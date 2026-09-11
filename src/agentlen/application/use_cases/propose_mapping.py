"""Application orchestration for AI mapping proposals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentlen.application.dto.mapping_document import document_to_mapping
from agentlen.application.errors import NotFoundError
from agentlen.application.ports.file_reader import FileProfiler, ProfileSanitizer
from agentlen.application.ports.structure_analyzer import StructureAnalyzer
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.application.use_cases.profile_file import ProfileFile, ProfileFileCommand
from agentlen.domain.model.mapping import Mapping, MappingProposal
from agentlen.domain.model.profile import FileProfile
from agentlen.domain.services import mapping_validator


@dataclass(frozen=True)
class StoredProposal:
    id: int
    proposal: MappingProposal

    @property
    def validation(self) -> dict[str, Any]:
        errors = mapping_validator.validate(self.proposal.mapping)
        return {
            "valid": not errors,
            "errors": [
                {"code": e.code, "field_path": e.field_path, "message": e.message} for e in errors
            ],
        }


class MappingValidationTools:
    """Provider-neutral tools backed by domain data and validation."""

    def __init__(self, profile: FileProfile) -> None:
        self._profile = profile

    async def execute(  # noqa: PLR0911 - one explicit branch per closed tool whitelist
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
        if tool_name == "get_field_profile":
            path = tool_input.get("path")
            field = next((f for f in self._profile.fields if f.path == path), None)
            return vars(field) if field else {"error": "Field not found"}
        if tool_name == "get_sample_values":
            path = tool_input.get("path")
            field = next((f for f in self._profile.fields if f.path == path), None)
            limit = min(int(tool_input.get("limit", 3)), 10)
            return (
                {"values": list(field.examples[:limit])} if field else {"error": "Field not found"}
            )
        if tool_name == "get_target_schema":
            # Read from the validator, not retyped here. A hardcoded list would
            # keep telling the model about the entities of the day it was
            # written, and the model would never learn about a new one.
            return {"entities": sorted(mapping_validator.VALID_TARGETS)}
        if tool_name == "validate_mapping":
            try:
                mapping = document_to_mapping(tool_input["mapping"])
            except (KeyError, TypeError, ValueError) as exc:
                return {"valid": False, "errors": [{"field_path": "mapping", "message": str(exc)}]}
            errors = mapping_validator.validate(mapping)
            return {
                "valid": not errors,
                "errors": [
                    {"code": e.code, "field_path": e.field_path, "message": e.message}
                    for e in errors
                ],
            }
        if tool_name == "preview_import":
            return {"error": "Preview requires a saved mapping"}
        return {"error": "Tool not available"}


class ProposeMapping:
    def __init__(
        self,
        uow: UnitOfWork,
        analyzer: StructureAnalyzer,
        profiler: FileProfiler,
        sanitizer: ProfileSanitizer,
    ) -> None:
        self._uow = uow
        self._analyzer = analyzer
        self._profiler = profiler
        self._sanitizer = sanitizer

    async def execute(
        self,
        *,
        file_id: int,
        data_source_id: int | None,
        hint: str | None = None,
    ) -> StoredProposal:
        async with self._uow as uow:
            stored_file = await uow.file_uploads.get_by_id(file_id)
            if data_source_id is not None:
                stored_source = await uow.data_sources.get_by_id(data_source_id)
                if stored_source is None:
                    raise NotFoundError("DataSource", data_source_id)
        if stored_file is None:
            raise NotFoundError("File", file_id)
        profile = await ProfileFile(self._profiler).execute(
            ProfileFileCommand(
                file_id=file_id,
                path=stored_file.storage_path,
                format=stored_file.format,
            )
        )
        profile = self._sanitizer.sanitize(profile)
        proposal = await self._analyzer.run_agent_loop(
            profile, MappingValidationTools(profile), hint
        )
        # Validation is deliberately evaluated even when invalid; invalid
        # proposals remain normal, editable results.
        mapping_validator.validate(proposal.mapping)
        async with self._uow as uow:
            # Re-checked inside the write transaction. The check above ran
            # before the agent loop — up to `max_iterations` provider calls
            # ago — and a file deleted in that window would violate the
            # `file_upload_id` foreign key, surfacing as a driver error and a
            # 500 where the caller should see a 404.
            if await uow.file_uploads.get_by_id(file_id) is None:
                raise NotFoundError("File", file_id)
            if (
                data_source_id is not None
                and await uow.data_sources.get_by_id(data_source_id) is None
            ):
                raise NotFoundError("DataSource", data_source_id)
            proposal_id = await uow.mapping_proposals.save(
                proposal, file_upload_id=file_id, data_source_id=data_source_id
            )
            await uow.commit()
        return StoredProposal(proposal_id, proposal)


class GetMappingProposal:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, proposal_id: int) -> StoredProposal:
        async with self._uow as uow:
            proposal = await uow.mapping_proposals.get(proposal_id)
        if proposal is None:
            raise NotFoundError("Mapping proposal", proposal_id)
        return StoredProposal(proposal_id, proposal)


class PatchMappingProposal:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, proposal_id: int, mapping: Mapping) -> StoredProposal:
        current = await GetMappingProposal(self._uow).execute(proposal_id)
        changed = MappingProposal(
            mapping=mapping,
            rationale=current.proposal.rationale,
            ambiguities=current.proposal.ambiguities,
            unmapped_fields=current.proposal.unmapped_fields,
            analyzer_descriptor=current.proposal.analyzer_descriptor,
        )
        async with self._uow as uow:
            await uow.mapping_proposals.update(proposal_id, changed)
            await uow.commit()
        return StoredProposal(proposal_id, changed)
