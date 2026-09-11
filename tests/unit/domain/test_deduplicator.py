"""Tests for Deduplicator — covers the idempotence acceptance test.

Subject requirement: "réimporter le même fichier ne doit pas doubler les résultats".
The Deduplicator is the domain component responsible for this guarantee.
"""

import pytest

from agentlen.domain.services.deduplicator import Deduplicator


class TestNaturalKey:
    def test_same_data_produces_same_key(self):
        key1 = Deduplicator.natural_key("session", {"external_id": "abc"}, ["external_id"])
        key2 = Deduplicator.natural_key("session", {"external_id": "abc"}, ["external_id"])
        assert key1 == key2

    def test_different_external_id_produces_different_key(self):
        key1 = Deduplicator.natural_key("session", {"external_id": "abc"}, ["external_id"])
        key2 = Deduplicator.natural_key("session", {"external_id": "xyz"}, ["external_id"])
        assert key1 != key2

    def test_different_entity_target_produces_different_key(self):
        """A session and a model_call with the same field value must not collide."""
        key1 = Deduplicator.natural_key("session", {"external_id": "1"}, ["external_id"])
        key2 = Deduplicator.natural_key("model_call", {"external_id": "1"}, ["external_id"])
        assert key1 != key2

    def test_composite_key_uses_all_declared_fields(self):
        key1 = Deduplicator.natural_key(
            "model_call",
            {"session_external_id": "s1", "sequence_index": "0"},
            ["session_external_id", "sequence_index"],
        )
        key2 = Deduplicator.natural_key(
            "model_call",
            {"session_external_id": "s1", "sequence_index": "1"},  # different index
            ["session_external_id", "sequence_index"],
        )
        assert key1 != key2

    def test_missing_field_does_not_raise(self):
        """A missing key field must not crash — import continues with a warning upstream."""
        key = Deduplicator.natural_key("session", {}, ["external_id"])
        assert isinstance(key, str)


class TestContentHash:
    def test_same_payload_produces_same_hash(self):
        payload = {"session_id": "abc", "agent": "claude-code"}
        assert Deduplicator.content_hash(payload) == Deduplicator.content_hash(payload)

    def test_different_payload_produces_different_hash(self):
        p1 = {"session_id": "abc"}
        p2 = {"session_id": "xyz"}
        assert Deduplicator.content_hash(p1) != Deduplicator.content_hash(p2)

    def test_key_order_does_not_affect_hash(self):
        """Hash must be canonical — key order in the source JSON must not matter."""
        p1 = {"a": 1, "b": 2}
        p2 = {"b": 2, "a": 1}
        assert Deduplicator.content_hash(p1) == Deduplicator.content_hash(p2)

    def test_hash_is_64_char_hex_string(self):
        h = Deduplicator.content_hash({"x": 1})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestStorageIssue:
    """#189. A record jsonb cannot hold is rejected by path, never altered."""

    def test_a_json_payload_is_storable(self) -> None:
        payload = {"a": [1, 2.5, None, True], "b": {"c": "é"}, "d": "\\u0000 is only text"}
        assert Deduplicator.storage_issue(payload, line_number=1) is None

    @pytest.mark.parametrize(
        ("payload", "path"),
        [
            ({"prompt": "TRACE\x00"}, "$.prompt"),
            ({"a b": {"x": ["ok", "TRACE\ud800"]}}, '$["a b"].x[1]'),
            ({"score": float("nan")}, "$.score"),
            ({"blob": b"TRACE"}, "$.blob"),
            ({"TRACE\x00": 1}, "$"),
        ],
    )
    def test_an_unstorable_value_is_rejected_by_its_path(self, payload: dict, path: str) -> None:
        issue = Deduplicator.storage_issue(payload, line_number=7)

        assert issue is not None
        assert (issue.severity, issue.code, issue.line_number) == (
            "rejected",
            "UNSTORABLE_VALUE",
            7,
        )
        assert issue.field_path == path
        assert "TRACE" not in issue.message
