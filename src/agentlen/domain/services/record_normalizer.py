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


def reference_name(value: object) -> str | None:
    """The text form of a referential name: agent, provider, model or tool.

    Names are resolved and stored as text, and a non-string handed to SQL used
    to fail the whole import (#141). So a JSON number becomes its text (`123`
    gives `"123"`, the narrowing TransformationEngine applies to any string
    target), a blank string is no name at all (MAPPING_CONTRACT.md rule 4: an
    unknown value stays null), and a boolean or a structure raises: `True` is
    not a tool name.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"expected text or a number, received {type(value).__name__}")
    text = str(value)
    return text if text.strip() else None


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

    @staticmethod
    def _name(
        target: str,
        field_name: str,
        data: dict[str, Any],
        line_number: int | None,
        *,
        blank_is_error: bool = False,
    ) -> tuple[str | None, ImportIssue | None]:
        """A referential name from `data` as text, or the issue that stops it.

        `blank_is_error` is for a name the row cannot do without: a tool call
        must point at a `tool` row (`tool_id` is NOT NULL), so a blank name
        rejects it with an explanation instead of the import dropping it.
        """
        field_path = f"entities[target={target}].fields[target={field_name}]"
        raw = data.get(field_name)
        try:
            name = reference_name(raw)
        except ValueError as exc:
            message = f"'{field_name}' must be a name: {exc}."
        else:
            if name is not None or raw is None or not blank_is_error:
                return name, None
            message = f"'{field_name}' is blank: the {target} cannot be linked without it."
        return None, ImportIssue(
            severity="rejected",
            code="REFERENCE_NAME_INVALID",
            message=message,
            field_path=field_path,
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

        agent_name, name_issue = self._name(entity.target, "agent_name", data, line_number)
        if name_issue is not None:
            issues.append(name_issue)
            return None, issues

        try:
            session = Session(
                id=uuid4(),
                data_source_id=data_source_id,
                external_id=str(data["external_id"]),
                agent_name=agent_name,
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
            data = result["data"]
            sequence_index = data.get("sequence_index", result["source_index"])
            data = {**data, "sequence_index": sequence_index}

            natural_key_issue = self._check_natural_key(entity, data, line_number)
            if natural_key_issue is not None:
                issues.append(natural_key_issue)
                continue

            model_name, model_issue = self._name(entity.target, "model_name", data, line_number)
            provider_name, provider_issue = self._name(
                entity.target, "provider_name", data, line_number
            )
            name_issues = [issue for issue in (model_issue, provider_issue) if issue is not None]
            if name_issues:
                issues.extend(name_issues)
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
                        model_name=model_name,
                        provider_name=provider_name,
                        started_at=data.get("started_at"),
                        duration_ms=data.get("duration_ms"),
                        stop_reason=data.get("stop_reason"),
                        error_code=data.get("error_code"),
                    )
                )
            except (KeyError, ValueError) as exc:
                issues.append(self._construction_issue(entity.target, exc, line_number))
                continue

            if provider_name:
                references.append(ReferenceRequest(kind="provider", name=provider_name))
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
            data = result["data"]
            sequence_index = data.get("sequence_index", result["source_index"])
            data = {**data, "sequence_index": sequence_index}

            natural_key_issue = self._check_natural_key(entity, data, line_number)
            if natural_key_issue is not None:
                issues.append(natural_key_issue)
                continue

            tool_name, name_issue = self._name(
                entity.target, "tool_name", data, line_number, blank_is_error=True
            )
            if name_issue is not None:
                issues.append(name_issue)
                continue
            if tool_name is None:
                # Absent altogether, from a mapping that did not mark it required.
                issues.append(
                    self._construction_issue(entity.target, KeyError("tool_name"), line_number)
                )
                continue

            try:
                tool_calls.append(
                    ToolCall(
                        id=uuid4(),
                        session_id=session.id,
                        sequence_index=int(sequence_index),
                        tool_name=tool_name,
                        status=data.get("status", "unknown"),
                        duration_ms=data.get("duration_ms"),
                        error_message=data.get("error_message"),
                        started_at=data.get("started_at"),
                    )
                )
            except (KeyError, ValueError) as exc:
                issues.append(self._construction_issue(entity.target, exc, line_number))
                continue

            references.append(ReferenceRequest(kind="tool", name=tool_name))

        return tool_calls, issues, references
