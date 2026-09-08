from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Protocol

from agentlen.domain.errors import InvalidOperatorParamError, OperatorFailedError
from agentlen.domain.model.import_run import ImportIssue
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping


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
            results: list of {'entity': str, 'data': dict} for successfully
                     transformed entities.
            issues:  list of ImportIssue for each field/entity that failed.
        """
        results: list[dict[str, Any]] = []
        issues: list[ImportIssue] = []

        for entity_mapping in mapping.entities:
            if entity_mapping.iterate:
                rows = self._extract_rows(raw_record, entity_mapping.iterate)
            else:
                rows = [raw_record]

            for row in rows:
                entity_data, entity_issues = self._apply_entity(entity_mapping, row, line_number)
                issues.extend(entity_issues)
                if entity_data is not None:
                    results.append({"entity": entity_mapping.target, "data": entity_data})

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

            if value is None and field_rule.required:
                # A required field that failed → the whole entity is rejected
                rejected = True
            elif value is not None:
                data[field_rule.target] = value

        return (None if rejected else data), issues

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

    def _hash(self, row: dict[str, Any], sources: list[str], algorithm: str) -> str:
        """SHA-256 of the resolved `sources` values, canonicalized the same way
        as Deduplicator.content_hash (sorted keys, stable regardless of the
        order values were collected in) — used as a synthetic natural key.
        """
        if algorithm != "sha256":
            raise ValueError(f"Unsupported hash algorithm '{algorithm}'")
        values = {source: self._extract(row, source) for source in sources}
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
                    return str(value).lower() in ("true", "1", "yes")
                case _:
                    raise ValueError(f"Unknown cast target '{to}'")
        except (ValueError, TypeError) as exc:
            if on_error == "null":
                return None
            raise exc

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
            return float(value) * factor
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
