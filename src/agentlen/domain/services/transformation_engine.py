from __future__ import annotations

from typing import Any

from agentlen.domain.model.import_run import ImportIssue
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping


class TransformationEngine:
    """Applies a Mapping to a raw source record and produces entity dicts.

    Pure function: no I/O, no database, no network.
    On operator failure for a required field → returns an ImportIssue.
    Processing continues for other entities even when one fails.
    """

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
                entity_data, entity_issues = self._apply_entity(
                    entity_mapping, row, line_number
                )
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

        # Extract raw value from the record using the source path
        value = self._extract(row, rule.source)

        # Apply operators in order
        for op in rule.operators:
            try:
                value = self._apply_operator(op, value)
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

    def _apply_operator(self, op: dict[str, Any], value: object) -> object:  # noqa: PLR0911
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
            case "concat":
                return None  # placeholder — implemented in Lot C
            case "hash":
                return None  # placeholder — implemented in Lot C
            case "coalesce":
                return None  # placeholder — implemented in Lot C
            case "parse_datetime":
                return None  # placeholder — implemented in Lot C
            case "regex_extract":
                return None  # placeholder — implemented in Lot C (with re2)
            case "split_rows":
                return None  # placeholder
            case _:
                raise ValueError(f"Unknown operator '{op_name}'")

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
