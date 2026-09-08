from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from agentlen.domain.model.import_run import ImportIssue
from agentlen.domain.model.mapping import EntityMapping, Mapping
from agentlen.domain.model.model_call import ModelCall, TokenUsage
from agentlen.domain.model.reference import ReferenceRequest
from agentlen.domain.model.session import Session
from agentlen.domain.model.tool_call import ToolCall
from agentlen.domain.services.transformation_engine import TransformationEngine

_TOKEN_USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
)


@dataclass(frozen=True)
class NormalizationResult:
    """Domain entities assembled from one raw source record, plus what's left
    to do outside the domain: issues to report, and referential names that
    still need resolving to an id (no I/O happens here).
    """

    sessions: tuple[Session, ...] = field(default_factory=tuple)
    model_calls: tuple[ModelCall, ...] = field(default_factory=tuple)
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)
    issues: tuple[ImportIssue, ...] = field(default_factory=tuple)
    reference_requests: tuple[ReferenceRequest, ...] = field(default_factory=tuple)


class RecordNormalizer:
    """Assembles TransformationEngine's flat field values into linked domain entities.

    One Mapping is assumed to declare at most one EntityMapping per target
    ('session', 'model_call', 'tool_call') — consistent with how mappings are
    authored throughout the project.
    """

    def __init__(self) -> None:
        self._engine = TransformationEngine()

    def normalize(
        self,
        mapping: Mapping,
        raw: dict[str, Any],
        *,
        data_source_id: int,
        line_number: int | None = None,
    ) -> NormalizationResult:
        entities_by_target = {e.target: e for e in mapping.entities}
        results, issues = self._engine.apply(mapping, raw, line_number)
        issues = list(issues)
        references: list[ReferenceRequest] = []

        session_rows = [r["data"] for r in results if r["entity"] == "session"]
        session_entity = entities_by_target.get("session")
        session: Session | None = None
        if session_rows and session_entity is not None:
            session, natural_key_issue = self._build_session(
                session_entity, session_rows[0], data_source_id, line_number
            )
            if natural_key_issue is not None:
                issues.append(natural_key_issue)
                session = None
            elif session is not None and session.agent_name:
                references.append(ReferenceRequest(kind="agent", name=session.agent_name))

        model_calls: list[ModelCall] = []
        model_call_entity = entities_by_target.get("model_call")
        if model_call_entity is not None:
            rows = [r["data"] for r in results if r["entity"] == "model_call"]
            model_calls, mc_issues, mc_refs = self._build_model_calls(
                model_call_entity, rows, session, line_number
            )
            issues.extend(mc_issues)
            references.extend(mc_refs)

        tool_calls: list[ToolCall] = []
        tool_call_entity = entities_by_target.get("tool_call")
        if tool_call_entity is not None:
            rows = [r["data"] for r in results if r["entity"] == "tool_call"]
            tool_calls, tc_issues, tc_refs = self._build_tool_calls(
                tool_call_entity, rows, session, line_number
            )
            issues.extend(tc_issues)
            references.extend(tc_refs)

        return NormalizationResult(
            sessions=tuple([session] if session is not None else []),
            model_calls=tuple(model_calls),
            tool_calls=tuple(tool_calls),
            issues=tuple(issues),
            reference_requests=tuple(references),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_natural_key(
        self, entity: EntityMapping, data: dict[str, Any], line_number: int | None
    ) -> ImportIssue | None:
        missing = [key for key in entity.natural_key if data.get(key) is None]
        if missing:
            return ImportIssue(
                severity="rejected",
                code="MAPPING_MISSING_NATURAL_KEY",
                message=f"Entity '{entity.target}' is missing natural key field(s): {missing}.",
                line_number=line_number,
            )
        return None

    def _build_session(
        self,
        entity: EntityMapping,
        data: dict[str, Any],
        data_source_id: int,
        line_number: int | None,
    ) -> tuple[Session | None, ImportIssue | None]:
        issue = self._check_natural_key(entity, data, line_number)
        if issue is not None:
            return None, issue

        session = Session(
            id=uuid4(),
            data_source_id=data_source_id,
            external_id=str(data["external_id"]),
            agent_name=data.get("agent_name"),
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
            duration_ms=data.get("duration_ms"),
            outcome=data.get("outcome"),
        )
        return session, None

    def _build_model_calls(
        self,
        entity: EntityMapping,
        rows: list[dict[str, Any]],
        session: Session | None,
        line_number: int | None,
    ) -> tuple[list[ModelCall], list[ImportIssue], list[ReferenceRequest]]:
        model_calls: list[ModelCall] = []
        issues: list[ImportIssue] = []
        references: list[ReferenceRequest] = []

        for index, data in enumerate(rows):
            if session is None:
                issues.append(
                    ImportIssue(
                        severity="rejected",
                        code="PARENT_SESSION_MISSING",
                        message="model_call has no session to attach to "
                        "(the session for this record was rejected).",
                        line_number=line_number,
                    )
                )
                continue

            sequence_index = data.get("sequence_index", index)
            data = {**data, "sequence_index": sequence_index}

            natural_key_issue = self._check_natural_key(entity, data, line_number)
            if natural_key_issue is not None:
                issues.append(natural_key_issue)
                continue

            token_usage = TokenUsage(
                **{key: data.get(key) for key in _TOKEN_USAGE_FIELDS}
            )
            model_calls.append(
                ModelCall(
                    id=uuid4(),
                    session_id=session.id,
                    sequence_index=sequence_index,
                    token_usage=token_usage,
                    status=data.get("status", "unknown"),
                    model_name=data.get("model_name"),
                    provider_name=data.get("provider_name"),
                    started_at=data.get("started_at"),
                    duration_ms=data.get("duration_ms"),
                    stop_reason=data.get("stop_reason"),
                    error_code=data.get("error_code"),
                )
            )
            if data.get("provider_name"):
                references.append(ReferenceRequest(kind="provider", name=data["provider_name"]))
            if data.get("model_name"):
                references.append(ReferenceRequest(kind="model", name=data["model_name"]))

        return model_calls, issues, references

    def _build_tool_calls(
        self,
        entity: EntityMapping,
        rows: list[dict[str, Any]],
        session: Session | None,
        line_number: int | None,
    ) -> tuple[list[ToolCall], list[ImportIssue], list[ReferenceRequest]]:
        tool_calls: list[ToolCall] = []
        issues: list[ImportIssue] = []
        references: list[ReferenceRequest] = []

        for index, data in enumerate(rows):
            if session is None:
                issues.append(
                    ImportIssue(
                        severity="rejected",
                        code="PARENT_SESSION_MISSING",
                        message="tool_call has no session to attach to "
                        "(the session for this record was rejected).",
                        line_number=line_number,
                    )
                )
                continue

            sequence_index = data.get("sequence_index", index)
            data = {**data, "sequence_index": sequence_index}

            natural_key_issue = self._check_natural_key(entity, data, line_number)
            if natural_key_issue is not None:
                issues.append(natural_key_issue)
                continue

            tool_calls.append(
                ToolCall(
                    id=uuid4(),
                    session_id=session.id,
                    sequence_index=sequence_index,
                    tool_name=str(data["tool_name"]),
                    status=data.get("status", "unknown"),
                    duration_ms=data.get("duration_ms"),
                    error_message=data.get("error_message"),
                    started_at=data.get("started_at"),
                )
            )
            if data.get("tool_name"):
                references.append(ReferenceRequest(kind="tool", name=data["tool_name"]))

        return tool_calls, issues, references
