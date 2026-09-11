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

#: Width of one source record's range in a derived call index: an iterated call
#: without a mapped `sequence_index` gets `(rank - 1) * RECORD_STRIDE + position`
#: (MAPPING_CONTRACT.md §2.2).
RECORD_STRIDE = 1_000

#: `sequence_index` is an INTEGER column; a larger value would fail the whole batch.
_MAX_SEQUENCE_INDEX = 2**31 - 1


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

        session_entries = [r for r in results if r["entity"] == "session"]
        session_entity = entities_by_target.get("session")
        session: Session | None = None
        if session_entries and session_entity is not None:
            session, session_issues = self._build_session(
                session_entity, session_entries, data_source_id, line_number
            )
            issues.extend(session_issues)
            if session is not None and session.agent_name:
                references.append(ReferenceRequest(kind="agent", name=session.agent_name))

        model_calls: list[ModelCall] = []
        model_call_entity = entities_by_target.get("model_call")
        if model_call_entity is not None:
            entries = [r for r in results if r["entity"] == "model_call"]
            model_calls, mc_issues, mc_refs = self._build_model_calls(
                model_call_entity, entries, session, line_number
            )
            issues.extend(mc_issues)
            references.extend(mc_refs)

        tool_calls: list[ToolCall] = []
        tool_call_entity = entities_by_target.get("tool_call")
        if tool_call_entity is not None:
            entries = [r for r in results if r["entity"] == "tool_call"]
            tool_calls, tc_issues, tc_refs = self._build_tool_calls(
                tool_call_entity, entries, session, line_number
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

    @staticmethod
    def _sequence_index(
        entity: EntityMapping, result: dict[str, Any], line_number: int | None
    ) -> tuple[Any, ImportIssue | None]:
        """The call's key within its session (MAPPING_CONTRACT.md §2.2).

        A mapped value is kept as it is: the mapping vouches that it is unique
        within the session. Without one, an iterated call only knows its
        position in this record's list, which restarts at 0 on every record —
        TraceLab writes one round per line, so every round reused the first
        round's keys (#188). The record's rank is folded in to keep lines apart.
        A non-iterated entity keeps its position, always 0 (#134).
        """
        data = result["data"]
        if "sequence_index" in data:
            sequence_index = data["sequence_index"]
        elif entity.iterate is not None:
            rank = (line_number or 1) - 1
            sequence_index = rank * RECORD_STRIDE + result["source_index"]
        else:
            sequence_index = result["source_index"]

        if isinstance(sequence_index, int) and sequence_index > _MAX_SEQUENCE_INDEX:
            return None, ImportIssue(
                severity="rejected",
                code="SEQUENCE_INDEX_OUT_OF_RANGE",
                message=(
                    f"'{entity.target}' sequence_index {sequence_index} exceeds "
                    f"{_MAX_SEQUENCE_INDEX}, the largest value the column holds."
                ),
                field_path=f"entities[target={entity.target}].fields[target=sequence_index]",
                line_number=line_number,
            )
        return sequence_index, None

    @staticmethod
    def _construction_issue(target: str, exc: Exception, line_number: int | None) -> ImportIssue:
        """A mapping can pass MappingValidator and still describe a field the
        target entity's __post_init__ rejects (e.g. status='success' where
        only ok/error/unknown are valid), or omit a field this normalizer
        indexes directly without it being in `natural_key`. Neither is a bug
        in this row alone — but the contract is "one bad row is explained
        and rejected, the rest of the import continues", not "one bad row
        takes down the whole run".
        """
        return ImportIssue(
            severity="rejected",
            code="ENTITY_CONSTRUCTION_FAILED",
            message=f"Could not build '{target}': {exc}",
            line_number=line_number,
        )

    @staticmethod
    def _parent_missing_issue(target: str, count: int, line_number: int | None) -> ImportIssue:
        return ImportIssue(
            severity="rejected",
            code="PARENT_SESSION_MISSING",
            message=(
                f"{count} '{target}' row(s) have no session to attach to "
                "(the session for this record was rejected)."
            ),
            line_number=line_number,
        )

    def _build_session(
        self,
        entity: EntityMapping,
        entries: list[dict[str, Any]],
        data_source_id: int,
        line_number: int | None,
    ) -> tuple[Session | None, list[ImportIssue]]:
        issues: list[ImportIssue] = []
        if len(entries) > 1:
            # Nothing in EntityMapping or MappingValidator forbids `iterate`
            # on the session entity, or two EntityMappings both targeting
            # 'session'. Silently keeping only the first would drop real
            # sessions with zero trace of why.
            issues.append(
                ImportIssue(
                    severity="warning",
                    code="MULTIPLE_SESSIONS_IGNORED",
                    message=(
                        f"{len(entries)} session rows produced from one source record; "
                        "only the first is kept, the rest are discarded."
                    ),
                    line_number=line_number,
                )
            )

        data = entries[0]["data"]
        natural_key_issue = self._check_natural_key(entity, data, line_number)
        if natural_key_issue is not None:
            issues.append(natural_key_issue)
            return None, issues

        try:
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
        except (KeyError, ValueError) as exc:
            issues.append(self._construction_issue(entity.target, exc, line_number))
            return None, issues

        return session, issues

    def _build_model_calls(
        self,
        entity: EntityMapping,
        entries: list[dict[str, Any]],
        session: Session | None,
        line_number: int | None,
    ) -> tuple[list[ModelCall], list[ImportIssue], list[ReferenceRequest]]:
        model_calls: list[ModelCall] = []
        issues: list[ImportIssue] = []
        references: list[ReferenceRequest] = []

        if session is None:
            if entries:
                issues.append(self._parent_missing_issue(entity.target, len(entries), line_number))
            return model_calls, issues, references

        for result in entries:
            sequence_index, index_issue = self._sequence_index(entity, result, line_number)
            if index_issue is not None:
                issues.append(index_issue)
                continue
            data = {**result["data"], "sequence_index": sequence_index}

            natural_key_issue = self._check_natural_key(entity, data, line_number)
            if natural_key_issue is not None:
                issues.append(natural_key_issue)
                continue

            try:
                token_usage = TokenUsage(**{key: data.get(key) for key in _TOKEN_USAGE_FIELDS})
                model_calls.append(
                    ModelCall(
                        id=uuid4(),
                        session_id=session.id,
                        sequence_index=int(sequence_index),
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
            except (KeyError, ValueError) as exc:
                issues.append(self._construction_issue(entity.target, exc, line_number))
                continue

            provider_name = data.get("provider_name")
            if provider_name:
                references.append(ReferenceRequest(kind="provider", name=provider_name))
            model_name = data.get("model_name")
            if model_name:
                # 'model' is unique on (provider_id, name) (DATA_MODEL.md §4) —
                # without the provider in context, resolution has nothing to
                # link the model to, and two providers publishing a same-named
                # model would collapse into a single row.
                context = (("provider_name", provider_name),) if provider_name else ()
                references.append(ReferenceRequest(kind="model", name=model_name, context=context))

        return model_calls, issues, references

    def _build_tool_calls(
        self,
        entity: EntityMapping,
        entries: list[dict[str, Any]],
        session: Session | None,
        line_number: int | None,
    ) -> tuple[list[ToolCall], list[ImportIssue], list[ReferenceRequest]]:
        tool_calls: list[ToolCall] = []
        issues: list[ImportIssue] = []
        references: list[ReferenceRequest] = []

        if session is None:
            if entries:
                issues.append(self._parent_missing_issue(entity.target, len(entries), line_number))
            return tool_calls, issues, references

        for result in entries:
            sequence_index, index_issue = self._sequence_index(entity, result, line_number)
            if index_issue is not None:
                issues.append(index_issue)
                continue
            data = {**result["data"], "sequence_index": sequence_index}

            natural_key_issue = self._check_natural_key(entity, data, line_number)
            if natural_key_issue is not None:
                issues.append(natural_key_issue)
                continue

            try:
                tool_calls.append(
                    ToolCall(
                        id=uuid4(),
                        session_id=session.id,
                        sequence_index=int(sequence_index),
                        tool_name=str(data["tool_name"]),
                        status=data.get("status", "unknown"),
                        duration_ms=data.get("duration_ms"),
                        error_message=data.get("error_message"),
                        started_at=data.get("started_at"),
                    )
                )
            except (KeyError, ValueError) as exc:
                issues.append(self._construction_issue(entity.target, exc, line_number))
                continue

            tool_name = data.get("tool_name")
            if tool_name:
                references.append(ReferenceRequest(kind="tool", name=tool_name))

        return tool_calls, issues, references
