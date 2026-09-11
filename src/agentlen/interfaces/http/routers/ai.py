"""AI provider discovery and editable mapping proposals."""

from __future__ import annotations

from fastapi import APIRouter

from agentlen.application.dto.mapping_document import document_to_mapping, mapping_to_document
from agentlen.application.errors import NotFoundError
from agentlen.application.use_cases.profile_file import ProfileFile, ProfileFileCommand
from agentlen.application.use_cases.propose_mapping import (
    GetMappingProposal,
    PatchMappingProposal,
    ProposeMapping,
    RefineMapping,
    StoredProposal,
)
from agentlen.domain.model.profile import FileProfile
from agentlen.interfaces.http.dependencies import (
    AnalyzerFactoryDep,
    FileProfilerDep,
    ProviderStatusDep,
    UnitOfWorkDep,
)
from agentlen.interfaces.http.schemas.ai import (
    ProposalMessageRequest,
    ProposalPatchRequest,
    ProposalRequest,
    ProposalResponse,
)

router = APIRouter(tags=["AI mapping"])


@router.get("/ai/providers")
async def providers(status: ProviderStatusDep) -> dict[str, object]:
    return status


async def _profile(file_id: int, uow: UnitOfWorkDep, profiler: FileProfilerDep) -> FileProfile:
    async with uow as transaction:
        stored = await transaction.file_uploads.get_by_id(file_id)
    if stored is None:
        raise NotFoundError("File", file_id)
    return await ProfileFile(profiler).execute(
        ProfileFileCommand(file_id=file_id, path=stored.storage_path)
    )


def _response(stored: StoredProposal) -> ProposalResponse:
    proposal = stored.proposal
    return ProposalResponse(
        proposal_id=stored.id,
        analyzer=proposal.analyzer_descriptor,
        mapping=mapping_to_document(proposal.mapping),
        validation=stored.validation,
        rationale=list(proposal.rationale),
        ambiguities=list(proposal.ambiguities),
        unmapped_fields=list(proposal.unmapped_fields),
    )


@router.post("/mappings/proposals", response_model=ProposalResponse)
async def propose(
    body: ProposalRequest,
    uow: UnitOfWorkDep,
    profiler: FileProfilerDep,
    analyzer_factory: AnalyzerFactoryDep,
) -> ProposalResponse:
    profile = await _profile(body.file_id, uow, profiler)
    analyzer = analyzer_factory(body.provider, body.model)
    result = await ProposeMapping(uow, analyzer).execute(
        file_id=body.file_id,
        data_source_id=body.data_source_id,
        profile=profile,
        hint=body.hint,
    )
    return _response(result)


@router.get("/mappings/proposals/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(proposal_id: int, uow: UnitOfWorkDep) -> ProposalResponse:
    return _response(await GetMappingProposal(uow).execute(proposal_id))


@router.post("/mappings/proposals/{proposal_id}/messages", response_model=ProposalResponse)
async def refine(
    proposal_id: int,
    body: ProposalMessageRequest,
    uow: UnitOfWorkDep,
    analyzer_factory: AnalyzerFactoryDep,
) -> ProposalResponse:
    current = await GetMappingProposal(uow).execute(proposal_id)
    # Refinement validation only needs the mapping tools; an empty profile does
    # not expose source data and keeps the provider call server-side.
    profile = FileProfile(
        file_id=0, format=current.proposal.mapping.source_format, record_count=0, sampled_records=0
    )
    analyzer = analyzer_factory(
        str(current.proposal.analyzer_descriptor["provider"]),
        str(current.proposal.analyzer_descriptor["model"]),
    )
    return _response(await RefineMapping(uow, analyzer).execute(proposal_id, body.message, profile))


@router.patch("/mappings/proposals/{proposal_id}", response_model=ProposalResponse)
async def patch_proposal(
    proposal_id: int, body: ProposalPatchRequest, uow: UnitOfWorkDep
) -> ProposalResponse:
    document = body.model_dump()
    mapping = document_to_mapping(document)
    return _response(await PatchMappingProposal(uow).execute(proposal_id, mapping))
