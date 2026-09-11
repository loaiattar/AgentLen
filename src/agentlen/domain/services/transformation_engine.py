from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from typing import Any, Protocol

from agentlen.domain.errors import InvalidOperatorParamError, OperatorFailedError
from agentlen.domain.model.import_run import ImportIssue
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.model.target_schema import TARGET_FIELD_TYPES

# Unit conversions land on fields typed `int` in TARGET_FIELD_TYPES, so their
# result is rounded to an integer. Kept next to the conversion that uses it;
# adding a target unit to _FACTORS without listing it here emits a float, which
# the type gate then has to round on its behalf.
_INTEGER_TARGET_UNITS = frozenset({"ms", "b"})


class RegexExtractor(Protocol):
    """Extracts one capture group from a string using a compiled pattern.

    A port, not a stdlib call: `domain/` is not allowed to import `re2`
    (import-linter — re2 usage is meant to stay centralized in
    `infrastructure/`, same as the sanitizer's). The concrete
    implementation (infra/text/re2_regex_extractor.py) is injected by
    whoever constructs the engine.
    """

    def extract(self, value: str, pattern: str, group: int) -> str | None: ...


class TransformationEngine:
    """Applies a Mapping to a raw source record and produces entity dicts.

    Pure function: no I/O, no database, no network — `regex_extract` is the
    one operator that needs a capability domain/ can't provide itself
    (linear-time regex matching), so it's injected via `RegexExtractor`
    rather than imported directly.
    On operator failure for a required field → returns an ImportIssue.
    Processing continues for other entities even when one fails.
    """

    def __init__(self, regex_extractor: RegexExtractor | None = None) -> None:
        self._regex_extractor = regex_extractor

    def apply(
        self,
        mapping: Mapping,
        raw_record: dict[str, Any],
        line_number: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[ImportIssue]]:
        """Transform one raw record according to the mapping.

        Returns:
            results: list of {'entity': str, 'data': dict, 'source_index': int}
                     for successfully transformed entities. `source_index` is
                     the entity's position in the *source* list (before any
                     rejection) — callers that need a stable, reimport-safe
                     ordering (e.g. a natural key) must use this, not their
                     own rank among survivors, which shifts whenever an
                     earlier row is rejected.
            issues:  list of ImportIssue for each field/entity that failed.
        """
        results: list[dict[str, Any]] = []
        issues: list[ImportIssue] = []

        for entity_mapping in mapping.entities:
            if entity_mapping.iterate:
                rows = self._extract_rows(raw_record, entity_mapping.iterate)
            else:
                rows = [raw_record]

            for source_index, row in enumerate(rows):
                entity_data, entity_issues = self._apply_entity(entity_mapping, row, line_number)
                issues.extend(entity_issues)
                if entity_data is not None:
                    results.append(
                        {
                            "entity": entity_mapping.target,
                            "data": entity_data,
                            "source_index": source_index,
                        }
                    )

        return results, issues

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_entity(
        self,
        entity: EntityMapping,
        row: dict[str, Any],
        line_number: int | None,
    ) -> tuple[dict[str, Any] | None, list[ImportIssue]]:
        data: dict[str, Any] = {}
        issues: list[ImportIssue] = []
        rejected = False

        for field_rule in entity.fields:
            value, field_issues = self._apply_field(field_rule, row, entity.target, line_number)
            issues.extend(field_issues)

            if value is not None:
                coerced, ok = self._coerce_target_type(entity.target, field_rule.target, value)
                if ok:
                    value = coerced
                else:
                    expected_name = self._expected_type_name(entity.target, field_rule.target)
                    # Same policy as a failed operator: a required field rejects
                    # the entity, an optional one drops its value and lets the
                    # rest of the row through. A natural-key field counts as
                    # required whatever the rule says — dropping it would let
                    # the normalizer fall back to the positional index and give
                    # the row a different identity, silently.
                    critical = field_rule.required or field_rule.target in entity.natural_key
                    issues.append(
                        ImportIssue(
                            severity="rejected" if critical else "warning",
                            code="TYPE_MISMATCH",
                            message=(
                                f"Field '{field_rule.target}' received "
                                f"{type(value).__name__}; expected {expected_name}."
                            ),
                            field_path=(
                                f"entities[target={entity.target}]"
                                f".fields[target={field_rule.target}]"
                            ),
                            line_number=line_number,
                        )
                    )
                    if critical:
                        rejected = True
                        continue
                    value = None

            if value is None and field_rule.required:
                # A required field that failed → the whole entity is rejected.
                # If it failed silently (absent from the source, no operator
                # exception), field_issues is empty — still record why.
                rejected = True
                if not field_issues:
                    issues.append(
                        ImportIssue(
                            severity="rejected",
                            code="MISSING_REQUIRED_FIELD",
                            message=f"Required field '{field_rule.target}' is missing or null.",
                            field_path=(
                                f"entities[target={entity.target}]"
                                f".fields[target={field_rule.target}]"
                            ),
                            line_number=line_number,
                        )
                    )
            elif value is not None:
                data[field_rule.target] = value

        return (None if rejected else data), issues

    @staticmethod
    def _has_target_type(entity_target: str, field_target: str, value: object) -> bool:
        expected = TARGET_FIELD_TYPES.get(entity_target, {}).get(field_target)
        if expected is None:
            return True
        # bool is an int subclass in Python, but false/true are never valid
        # token counts, durations or sequence indices.
        if expected is int and isinstance(value, bool):
            return False
        return isinstance(value, expected)

    @staticmethod
    def _coerce_target_type(
        entity_target: str, field_target: str, value: object
    ) -> tuple[object, bool]:
        """Narrow a value to its target type, or report that it cannot be.

        `RecordNormalizer` already coerces one layer down —
        `str(data["external_id"])`, `str(data["tool_name"])`. Rejecting here
        what it would have accepted there turns files that imported cleanly
        into files that import nothing, and the AI prompt's own canonical
        example maps `$.run_id` onto `external_id` with no cast operator.

        So this narrows two cases only — a JSON number onto a string field, and
        a float onto an integer field — and refuses everything else, including
        the numeric string that a `cast` operator is there to handle.
        """
        if TransformationEngine._has_target_type(entity_target, field_target, value):
            return value, True

        expected = TARGET_FIELD_TYPES.get(entity_target, {}).get(field_target)

        # A JSON number landing on a string field: the normalizer would `str()`
        # it. `bool` stays out — `"True"` is not an outcome or a status.
        if expected is str and isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value), True

        if expected is int and not isinstance(value, bool):
            # A float on an int field is normally a representation artefact of a
            # unit conversion, not a different value.
            if isinstance(value, float):
                if math.isfinite(value):
                    return round(value), True
                return value, False
            # A numeric *string* is deliberately not coerced here: the PR's
            # own test pins `"7"` onto `sequence_index` as a TYPE_MISMATCH, and
            # a mapping that means it should say so with a `cast` operator.

        return value, False

    @staticmethod
    def _expected_type_name(entity_target: str, field_target: str) -> str:
        expected = TARGET_FIELD_TYPES[entity_target][field_target]
        assert expected is not None
        if isinstance(expected, tuple):
            return " or ".join(item.__name__ for item in expected)
        return expected.__name__

    def _apply_field(
        self,
        rule: FieldRule,
        row: dict[str, Any],
        entity_target: str,
        line_number: int | None,
    ) -> tuple[object | None, list[ImportIssue]]:
        field_path = f"entities[target={entity_target}].fields[target={rule.target}]"

        # Extract raw value from the record using the source path. Operators that
        # combine several source fields (coalesce/concat/hash) ignore this and
        # resolve their own `sources` list against `row` instead.
        value = self._extract(row, rule.source)

        # Apply operators in order
        for op in rule.operators:
            try:
                value = self._apply_operator(op, value, row)
            except (OperatorFailedError, InvalidOperatorParamError) as exc:
                issue = ImportIssue(
                    severity="rejected" if rule.required else "warning",
                    code=exc.code,
                    message=str(exc.message),
                    field_path=field_path,
                    line_number=line_number,
                )
                return None, [issue]
            except Exception as exc:  # noqa: BLE001
                issue = ImportIssue(
                    severity="rejected" if rule.required else "warning",
                    code="OPERATOR_FAILED",
                    message=f"Operator '{op.get('op')}' failed: {exc}",
                    field_path=field_path,
                    line_number=line_number,
                )
                return None, [issue]

        return value, []

    def _extract(self, record: dict[str, Any], source_path: str) -> object | None:
        """Extract a value from a dict using a simple dot/bracket path.

        Supports '$.field' and '$.nested.field' notation.
        Returns None when the path doesn't exist.
        """
        if source_path.startswith("$."):
            source_path = source_path[2:]
        elif source_path == "$":
            return record

        current: object = record
        for part in source_path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return current

    def _extract_rows(self, record: dict[str, Any], iterate_path: str) -> list[dict[str, Any]]:
        """Extract a list of sub-records using an iterate path.

        Only supports simple paths (no filter expressions at this stage).
        """
        value = self._extract(record, iterate_path)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    def _apply_operator(  # noqa: PLR0911, PLR0912
        self, op: dict[str, Any], value: object, row: dict[str, Any]
    ) -> object:
        op_name = op.get("op")

        match op_name:
            case "cast":
                return self._cast(value, op["to"], op.get("on_error", "reject"))
            case "default":
                return value if value is not None else op.get("value")
            case "trim":
                return str(value).strip() if value is not None else None
            case "lower":
                return str(value).lower() if value is not None else None
            case "upper":
                return str(value).upper() if value is not None else None
            case "unit_convert":
                return self._unit_convert(value, op["from"], op["to"])
            case "map_values":
                return self._map_values(value, op)
            case "json_passthrough":
                return value  # kept as-is, stored in JSONB
            case "parse_datetime":
                return self._parse_datetime(value, op["format"])
            case "coalesce":
                return self._coalesce(row, op["sources"])
            case "concat":
                return self._concat(row, op["sources"], op.get("separator", ""))
            case "hash":
                return self._hash(row, op["sources"], op.get("algorithm", "sha256"))
            case "regex_extract":
                return self._regex_extract(value, op["pattern"], op.get("group", 0))
            case "split_rows":
                return None  # placeholder
            case _:
                raise ValueError(f"Unknown operator '{op_name}'")

    @staticmethod
    def _parse_datetime(value: object, fmt: str) -> datetime | None:
        """Parse `value` into a UTC-aware datetime, or raise DATETIME_PARSE_FAILED.

        `fmt` is one of the built-in tokens ('iso8601', 'unix_seconds',
        'unix_millis') or a strptime pattern. Never falls back to a default
        date on failure — that's the caller's job via ImportIssue.
        """
        if value is None:
            return None
        try:
            if fmt == "iso8601":
                text = str(value).replace("Z", "+00:00")
                parsed = datetime.fromisoformat(text)
            elif fmt == "unix_seconds":
                parsed = datetime.fromtimestamp(float(value), tz=UTC)  # type: ignore[arg-type]
            elif fmt == "unix_millis":
                parsed = datetime.fromtimestamp(float(value) / 1000, tz=UTC)  # type: ignore[arg-type]
            else:
                parsed = datetime.strptime(str(value), fmt)  # noqa: DTZ007
        except (ValueError, TypeError, OSError, OverflowError) as exc:
            raise OperatorFailedError(
                code="DATETIME_PARSE_FAILED",
                message=f"Cannot parse {value!r} with format {fmt!r}: {exc}",
            ) from exc

        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)

    def _coalesce(self, row: dict[str, Any], sources: list[str]) -> object:
        """First non-null value among `sources`, or None if all are null."""
        for source in sources:
            resolved = self._extract(row, source)
            if resolved is not None:
                return resolved
        return None

    def _concat(self, row: dict[str, Any], sources: list[str], separator: str) -> str | None:
        """Join the non-null values of `sources` with `separator`.

        A null source is skipped. If every source is null, returns None
        rather than an empty string.
        """
        parts = [str(v) for s in sources if (v := self._extract(row, s)) is not None]
        return separator.join(parts) if parts else None

    def _hash(self, row: dict[str, Any], sources: list[str], algorithm: str) -> str | None:
        """SHA-256 of the resolved `sources` values, canonicalized the same way
        as Deduplicator.content_hash (sorted keys, stable regardless of the
        order values were collected in) — used as a synthetic natural key.
        """
        if algorithm != "sha256":
            raise ValueError(f"Unsupported hash algorithm '{algorithm}'")
        values = {source: self._extract(row, source) for source in sources}
        if all(value is None for value in values.values()):
            return None
        canonical = json.dumps(values, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _regex_extract(self, value: object, pattern: str, group: int) -> str | None:
        """Extract `group` from the first match of `pattern` in `value`.

        Delegates to the injected RegexExtractor (re2 in production: matching
        is linear in input size by construction, so a pathological pattern
        like `(a+)+$` can't cause catastrophic backtracking — the timeout
        guarantee from MAPPING_CONTRACT.md §3 is structural, not a fragile
        signal.alarm). `domain/` itself never imports re2 (import-linter).
        """
        if value is None:
            return None
        if self._regex_extractor is None:
            raise OperatorFailedError(
                code="REGEX_EXTRACTOR_NOT_CONFIGURED",
                message="regex_extract was used but no RegexExtractor was injected "
                "into this TransformationEngine.",
            )
        return self._regex_extractor.extract(str(value), pattern, group)

    @staticmethod
    def _cast(value: object, to: str, on_error: str) -> object:
        if value is None:
            return None
        # A CSV source yields `""` for an empty cell, never `None`. That is an
        # unknown value, and rule 4 of MAPPING_CONTRACT.md says an unknown value
        # stays unknown instead of failing the row or becoming an implicit 0.
        if isinstance(value, str) and not value.strip():
            return None
        try:
            match to:
                case "string":
                    return str(value)
                case "integer":
                    if isinstance(value, (int, float, str, bytes)):
                        return int(value)
                    raise ValueError(f"Cannot cast {type(value).__name__} to integer")
                case "float":
                    if isinstance(value, (int, float, str, bytes)):
                        return float(value)
                    raise ValueError(f"Cannot cast {type(value).__name__} to float")
                case "boolean":
                    if isinstance(value, bool):
                        return value
                    normalized = str(value).strip().lower()
                    if normalized in {"true", "1", "yes"}:
                        return True
                    if normalized in {"false", "0", "no"}:
                        return False
                    raise ValueError(f"Cannot cast {value!r} to boolean")
                case _:
                    raise ValueError(f"Unknown cast target '{to}'")
        except (ValueError, TypeError) as exc:
            if on_error == "null":
                return None
            raise OperatorFailedError(code="CAST_FAILED", message=str(exc)) from exc

    @staticmethod
    def _unit_convert(value: object, from_unit: str, to_unit: str) -> object:
        if value is None:
            return None
        _FACTORS: dict[tuple[str, str], float] = {
            ("s", "ms"): 1_000,
            ("min", "ms"): 60_000,
            ("ns", "ms"): 1 / 1_000_000,
            ("ms", "s"): 1 / 1_000,
            ("kb", "b"): 1_024,
            ("mb", "b"): 1_048_576,
        }
        key = (from_unit.lower(), to_unit.lower())
        factor = _FACTORS.get(key)
        if factor is None:
            raise ValueError(f"Unknown unit conversion '{from_unit}' → '{to_unit}'")
        if isinstance(value, (int, float, str, bytes)):
            converted = float(value) * factor
            # `int()` truncates toward zero, so binary representation error
            # became an off-by-one: 1.005 s * 1000 is 1004.9999999999999, and
            # `int()` stored 1004 ms. Sub-unit values still round to 0 — the
            # target column is an integer count of ms, and 0.4 ms really is 0 —
            # but that is the schema's floor, not an arithmetic mistake.
            return round(converted) if to_unit.lower() in _INTEGER_TARGET_UNITS else converted
        raise ValueError(f"Cannot convert {type(value).__name__} to float for unit conversion")

    @staticmethod
    def _map_values(value: object, op: dict[str, Any]) -> object:
        table: dict[str, Any] = op.get("table", {})
        on_unknown: str = op.get("on_unknown", "passthrough")
        str_value = str(value) if value is not None else "null"
        if str_value in table:
            return table[str_value]
        match on_unknown:
            case "passthrough":
                return value
            case "null":
                return None
            case "constant":
                return op.get("constant")
            case "reject":
                raise ValueError(f"Value '{value}' not in map_values table.")
            case _:
                return value
