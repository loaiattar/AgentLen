"""Tests for the six operators added by issue #43: parse_datetime, coalesce,
concat, hash, regex_extract, split_rows. One nominal + one failure case each,
as required by the ticket.
"""

from datetime import UTC, datetime
from uuid import uuid4

from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.services.transformation_engine import TransformationEngine

EXPECTED_FAILURE_LINE_NUMBER = 7


def _make_mapping(field: FieldRule, *, target: str = "session") -> Mapping:
    return Mapping(
        id=uuid4(),
        name="test",
        version=1,
        source_format="jsonl",
        entities=[EntityMapping(target=target, natural_key=["external_id"], fields=[field])],
    )


# ---------------------------------------------------------------------------
# parse_datetime
# ---------------------------------------------------------------------------


def test_parse_datetime_unix_seconds_and_iso8601_agree_on_the_same_instant():
    reference = datetime(2026, 9, 7, 9, 12, 3, tzinfo=UTC)
    unix_seconds = int(reference.timestamp())
    iso_text = reference.strftime("%Y-%m-%dT%H:%M:%SZ")

    engine = TransformationEngine()

    mapping_unix = _make_mapping(
        FieldRule(
            target="started_at",
            source="$.ts",
            required=True,
            operators=[{"op": "parse_datetime", "format": "unix_seconds"}],
        )
    )
    results_unix, issues_unix = engine.apply(mapping_unix, {"ts": unix_seconds})

    mapping_iso = _make_mapping(
        FieldRule(
            target="started_at",
            source="$.ts",
            required=True,
            operators=[{"op": "parse_datetime", "format": "iso8601"}],
        )
    )
    results_iso, issues_iso = engine.apply(mapping_iso, {"ts": iso_text})

    assert issues_unix == []
    assert issues_iso == []
    assert results_unix[0]["data"]["started_at"] == reference
    assert results_iso[0]["data"]["started_at"] == reference


def test_parse_datetime_unix_millis():
    reference = datetime(2026, 1, 1, tzinfo=UTC)
    millis = int(reference.timestamp() * 1000)

    engine = TransformationEngine()
    mapping = _make_mapping(
        FieldRule(
            target="started_at",
            source="$.ts",
            required=True,
            operators=[{"op": "parse_datetime", "format": "unix_millis"}],
        )
    )
    results, issues = engine.apply(mapping, {"ts": millis})

    assert issues == []
    assert results[0]["data"]["started_at"] == reference


def test_parse_datetime_strptime_pattern():
    engine = TransformationEngine()
    mapping = _make_mapping(
        FieldRule(
            target="started_at",
            source="$.ts",
            required=True,
            operators=[{"op": "parse_datetime", "format": "%d/%m/%Y"}],
        )
    )
    results, issues = engine.apply(mapping, {"ts": "07/09/2026"})

    assert issues == []
    assert results[0]["data"]["started_at"] == datetime(2026, 9, 7, tzinfo=UTC)


def test_parse_datetime_unparsable_value_produces_import_issue_not_a_default_date():
    engine = TransformationEngine()
    mapping = _make_mapping(
        FieldRule(
            target="started_at",
            source="$.ts",
            required=True,
            operators=[{"op": "parse_datetime", "format": "iso8601"}],
        )
    )
    results, issues = engine.apply(mapping, {"ts": "n/a"}, line_number=7)

    assert results == []
    assert len(issues) == 1
    assert issues[0].code == "DATETIME_PARSE_FAILED"
    assert issues[0].field_path is not None
    assert issues[0].line_number == EXPECTED_FAILURE_LINE_NUMBER
