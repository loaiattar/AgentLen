"""Tests for the six operators added by issue #43: parse_datetime, coalesce,
concat, hash, regex_extract, split_rows. One nominal + one failure case each,
as required by the ticket.
"""

import time
from datetime import UTC, datetime
from uuid import uuid4

from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.services.transformation_engine import TransformationEngine
from agentlen.infrastructure.text.re2_regex_extractor import Re2RegexExtractor

EXPECTED_FAILURE_LINE_NUMBER = 7
CATASTROPHIC_BACKTRACKING_TIMEOUT_SECONDS = 0.1


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


# ---------------------------------------------------------------------------
# coalesce
# ---------------------------------------------------------------------------


def test_coalesce_returns_first_non_null_source():
    engine = TransformationEngine()
    mapping = _make_mapping(
        FieldRule(
            target="external_id",
            source="$.unused",
            required=True,
            operators=[{"op": "coalesce", "sources": ["$.legacy_id", "$.id"]}],
        )
    )
    results, issues = engine.apply(mapping, {"legacy_id": None, "id": "abc"})

    assert issues == []
    assert results[0]["data"]["external_id"] == "abc"


def test_coalesce_all_sources_null_returns_none_not_empty_string_or_zero():
    engine = TransformationEngine()
    mapping = _make_mapping(
        FieldRule(
            target="outcome",
            source="$.unused",
            required=False,
            operators=[{"op": "coalesce", "sources": ["$.a", "$.b", "$.c"]}],
        )
    )
    results, issues = engine.apply(mapping, {})

    assert issues == []
    assert "outcome" not in results[0]["data"]  # None values are simply not set


# ---------------------------------------------------------------------------
# concat
# ---------------------------------------------------------------------------


def test_concat_joins_non_null_sources_with_separator():
    engine = TransformationEngine()
    mapping = _make_mapping(
        FieldRule(
            target="external_id",
            source="$.unused",
            required=True,
            operators=[{"op": "concat", "sources": ["$.project", "$.session"], "separator": ":"}],
        )
    )
    results, issues = engine.apply(mapping, {"project": "p1", "session": "s1"})

    assert issues == []
    assert results[0]["data"]["external_id"] == "p1:s1"


def test_concat_skips_null_sources_and_returns_none_if_all_null():
    engine = TransformationEngine()
    mapping = _make_mapping(
        FieldRule(
            target="outcome",
            source="$.unused",
            required=False,
            operators=[{"op": "concat", "sources": ["$.a", "$.b"], "separator": "-"}],
        )
    )
    results, issues = engine.apply(mapping, {})

    assert issues == []
    assert "outcome" not in results[0]["data"]


# ---------------------------------------------------------------------------
# hash
# ---------------------------------------------------------------------------


def _hash_mapping(sources: list[str]) -> Mapping:
    return _make_mapping(
        FieldRule(
            target="external_id",
            source="$.unused",
            required=True,
            operators=[{"op": "hash", "algorithm": "sha256", "sources": sources}],
        )
    )


def test_hash_is_stable_regardless_of_sources_declaration_order():
    engine = TransformationEngine()
    raw = {"a": "x", "b": "y"}

    results_ab, _ = engine.apply(_hash_mapping(["$.a", "$.b"]), raw)
    results_ba, _ = engine.apply(_hash_mapping(["$.b", "$.a"]), raw)

    assert results_ab[0]["data"]["external_id"] == results_ba[0]["data"]["external_id"]


def test_hash_unsupported_algorithm_is_rejected():
    engine = TransformationEngine()
    mapping = _make_mapping(
        FieldRule(
            target="external_id",
            source="$.unused",
            required=True,
            operators=[{"op": "hash", "algorithm": "md5", "sources": ["$.a"]}],
        )
    )
    results, issues = engine.apply(mapping, {"a": "x"})

    assert results == []
    assert len(issues) == 1
    assert issues[0].severity == "rejected"


def test_hash_returns_none_when_every_source_is_absent():
    results, issues = TransformationEngine().apply(_hash_mapping(["$.a", "$.b"]), {})

    assert results == []
    assert len(issues) == 1
    assert issues[0].code == "MISSING_REQUIRED_FIELD"


def test_boolean_cast_rejects_an_unknown_string_instead_of_returning_false():
    mapping = _make_mapping(
        FieldRule(
            target="external_id",
            source="$.value",
            required=True,
            operators=[{"op": "cast", "to": "boolean"}],
        )
    )

    results, issues = TransformationEngine().apply(mapping, {"value": "perhaps"})

    assert results == []
    assert len(issues) == 1
    assert issues[0].code == "CAST_FAILED"


# ---------------------------------------------------------------------------
# regex_extract
# ---------------------------------------------------------------------------


def test_regex_extract_returns_the_requested_group():
    engine = TransformationEngine(regex_extractor=Re2RegexExtractor())
    mapping = _make_mapping(
        FieldRule(
            target="external_id",
            source="$.raw",
            required=True,
            operators=[{"op": "regex_extract", "pattern": r"session-(\d+)", "group": 1}],
        )
    )
    results, issues = engine.apply(mapping, {"raw": "session-42"})

    assert issues == []
    assert results[0]["data"]["external_id"] == "42"


def test_regex_extract_invalid_pattern_produces_import_issue_with_a_readable_message():
    engine = TransformationEngine(regex_extractor=Re2RegexExtractor())
    mapping = _make_mapping(
        FieldRule(
            target="external_id",
            source="$.raw",
            required=True,
            operators=[{"op": "regex_extract", "pattern": "(unclosed", "group": 0}],
        )
    )
    results, issues = engine.apply(mapping, {"raw": "anything"})

    assert results == []
    assert len(issues) == 1
    assert issues[0].code == "INVALID_OPERATOR_PARAM"
    assert issues[0].message


def test_regex_extract_does_not_suffer_catastrophic_backtracking():
    # (a+)+$ is the textbook pattern that makes Python's stdlib `re` hang
    # exponentially on a long non-matching input. re2 must stay linear.
    engine = TransformationEngine(regex_extractor=Re2RegexExtractor())
    mapping = _make_mapping(
        FieldRule(
            target="external_id",
            source="$.raw",
            required=True,
            operators=[{"op": "regex_extract", "pattern": "(a+)+$", "group": 0}],
        )
    )
    pathological_input = "a" * 100 + "!"

    started = time.perf_counter()
    engine.apply(mapping, {"raw": pathological_input})
    elapsed = time.perf_counter() - started

    assert elapsed < CATASTROPHIC_BACKTRACKING_TIMEOUT_SECONDS


def test_regex_extract_without_a_configured_extractor_produces_a_clear_issue():
    # domain/ can't import re2 (import-linter) — the engine depends on the
    # RegexExtractor port instead. Using the operator without one configured
    # must fail clearly, not with an AttributeError deep in the call stack.
    engine = TransformationEngine()  # no regex_extractor injected
    mapping = _make_mapping(
        FieldRule(
            target="external_id",
            source="$.raw",
            required=True,
            operators=[{"op": "regex_extract", "pattern": r"(\d+)", "group": 1}],
        )
    )
    results, issues = engine.apply(mapping, {"raw": "session-42"})

    assert results == []
    assert len(issues) == 1
    assert issues[0].code == "REGEX_EXTRACTOR_NOT_CONFIGURED"


# ---------------------------------------------------------------------------
# unit_convert / empty values
# ---------------------------------------------------------------------------


def test_unit_convert_rounds_instead_of_truncating():
    """`int()` truncated toward zero, turning float error into an off-by-one.

    `1.005 * 1000` is `1004.9999999999999` in binary floating point, which
    `int()` stored as 1004 ms.
    """
    mapping = _make_mapping(
        FieldRule(
            target="duration_ms",
            source="$.dur",
            required=True,
            operators=[{"op": "unit_convert", "from": "s", "to": "ms"}],
        )
    )

    results, issues = TransformationEngine().apply(mapping, {"dur": 1.005})

    assert issues == []
    assert results[0]["data"]["duration_ms"] == 1005


def test_empty_source_value_is_unknown_not_a_cast_failure():
    """A CSV source yields `""` for an empty cell, never `None`.

    Rule 4 of MAPPING_CONTRACT.md: an unknown value stays unknown. On an
    optional field that means no value and no issue, not a rejected row.
    """
    mapping = Mapping(
        id=uuid4(),
        name="test",
        version=1,
        source_format="csv",
        entities=[
            EntityMapping(
                target="session",
                natural_key=["external_id"],
                fields=[
                    FieldRule(target="external_id", source="$.id", required=True),
                    FieldRule(
                        target="duration_ms",
                        source="$.dur",
                        operators=[{"op": "cast", "to": "integer"}],
                    ),
                ],
            )
        ],
    )

    results, issues = TransformationEngine().apply(mapping, {"id": "s1", "dur": "   "})

    assert issues == []
    assert len(results) == 1
    assert "duration_ms" not in results[0]["data"]
