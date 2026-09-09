"""Adapter behaviour, driven by recorded provider responses.

No network: each test feeds a captured payload through the adapter's own parser,
so what is exercised is the conversion the adapter is responsible for.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from agentlen.application.errors import AnalyzerError
from agentlen.domain.model.mapping import MappingProposal
from agentlen.infrastructure.ai.anthropic_adapter import AnthropicAnalyzer
from agentlen.infrastructure.ai.fake_adapter import FakeAnalyzer
from agentlen.infrastructure.ai.openai_adapter import OpenAIAnalyzer
from agentlen.infrastructure.config.settings import AISettings

PROPOSAL = json.dumps(
    {
        "mapping": {
            "name": "m",
            "source_format": "jsonl",
            "entities": [
                {
                    "target": "session",
                    "natural_key": ["external_id"],
                    "fields": [{"target": "external_id", "source": "$.sid", "required": True}],
                }
            ],
        },
        "rationale": [],
        "ambiguities": [{"field": "$.duration", "question": "s ou ms ?", "options": []}],
        "unmapped_fields": [{"path": "$.debug", "reason": "aucun équivalent"}],
    }
)


def anthropic() -> AnthropicAnalyzer:
    return AnthropicAnalyzer(AISettings(provider="anthropic", model="m"), "k")


def openai() -> OpenAIAnalyzer:
    return OpenAIAnalyzer(AISettings(provider="openai", model="m"), "k")


# ---------------------------------------------------------------------------
# Both providers converge on the same object
# ---------------------------------------------------------------------------


def test_both_adapters_produce_the_same_proposal_from_their_own_format() -> None:
    """The point of the port: two wire formats, one domain object. Without
    this, #22 could not compare the two models' output."""
    from_anthropic = anthropic()._parse_turn(
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": PROPOSAL}]}
    )
    from_openai = openai()._parse_turn(
        {"choices": [{"message": {"content": PROPOSAL, "role": "assistant"}}]}
    )

    a = anthropic()._to_proposal(from_anthropic.text)
    o = openai()._to_proposal(from_openai.text)

    assert isinstance(a, MappingProposal) and isinstance(o, MappingProposal)
    assert a.mapping.entities[0].target == o.mapping.entities[0].target == "session"
    assert a.ambiguities == o.ambiguities
    assert a.analyzer_descriptor["provider"] == "anthropic"
    assert o.analyzer_descriptor["provider"] == "openai"


def test_each_adapter_reads_tool_calls_out_of_its_own_shape() -> None:
    a = anthropic()._parse_turn(
        {
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "validate_mapping",
                    "input": {"mapping": {}},
                }
            ],
        }
    )
    o = openai()._parse_turn(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "t1",
                                "function": {
                                    "name": "validate_mapping",
                                    "arguments": '{"mapping": {}}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
    )

    for turn in (a, o):
        assert turn.stop_reason == "tool_use"
        assert turn.tool_calls[0].name == "validate_mapping"
        assert turn.tool_calls[0].arguments == {"mapping": {}}


def test_tool_results_are_sent_back_in_each_provider_shape() -> None:
    """Anthropic wants one message holding every result; OpenAI wants one
    message per result. Getting this backwards breaks the loop silently."""
    from agentlen.infrastructure.ai.base import ToolCall

    call = ToolCall(id="t1", name="validate_mapping", arguments={})
    results = [(call, {"valid": True})]

    a = anthropic()._tool_results_message(results)
    o = openai()._tool_results_message(results)

    assert isinstance(a, dict) and a["role"] == "user"
    assert a["content"][0]["tool_use_id"] == "t1"
    assert isinstance(o, list) and o[0]["role"] == "tool"
    assert o[0]["tool_call_id"] == "t1"


# ---------------------------------------------------------------------------
# A non-conforming answer is an error, never a patched-up mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["ambiguities", "unmapped_fields"])
def test_a_reply_missing_a_required_section_is_refused(missing: str) -> None:
    """MAPPING_CONTRACT.md §5: an adapter that does not return these is
    incomplete. Filling them with empty lists would hide that."""
    payload: dict[str, Any] = json.loads(PROPOSAL)
    del payload[missing]

    with pytest.raises(AnalyzerError) as exc:
        anthropic()._to_proposal(json.dumps(payload))
    assert missing in str(exc.value)


def test_a_reply_that_is_not_json_is_refused() -> None:
    with pytest.raises(AnalyzerError):
        anthropic()._to_proposal("Je pense que le mapping devrait ressembler à ceci…")


def test_json_wrapped_in_prose_or_fences_is_still_read() -> None:
    """Models routinely wrap the document in explanation or code fences.
    Refusing those would fail on a correct answer."""
    wrapped = f"Voici ma proposition :\n\n```json\n{PROPOSAL}\n```\n\nDis-moi si ça convient."
    assert anthropic()._to_proposal(wrapped).mapping.name == "m"


def test_unreadable_tool_arguments_are_reported_not_crashed() -> None:
    with pytest.raises(AnalyzerError) as exc:
        openai()._parse_turn(
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "t1",
                                    "function": {"name": "validate_mapping", "arguments": "{oops"},
                                }
                            ]
                        }
                    }
                ]
            }
        )
    assert "validate_mapping" in str(exc.value)


def test_a_reply_without_choices_names_the_likely_cause() -> None:
    """The commonest mistake with openai_compatible: a base_url that is not
    actually OpenAI-shaped."""
    with pytest.raises(AnalyzerError) as exc:
        openai()._parse_turn({"error": "not found"})
    assert "compatible OpenAI" in str(exc.value)


# ---------------------------------------------------------------------------
# The fake really simulates the loop
# ---------------------------------------------------------------------------


class RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(tool_name)
        return {"valid": True, "errors": []}


async def test_the_fake_calls_a_tool_before_answering() -> None:
    """A double that skipped the loop would let a broken loop pass the suite."""
    executor = RecordingExecutor()
    analyzer = FakeAnalyzer()

    proposal = await analyzer.run_agent_loop(profile={}, tool_executor=executor)

    assert executor.calls == ["validate_mapping"]
    assert proposal.mapping.entities
    assert proposal.ambiguities
    assert proposal.unmapped_fields


async def test_the_fake_needs_no_network_and_no_key() -> None:
    analyzer = FakeAnalyzer()
    assert analyzer.descriptor["provider"] == "fake"
    proposal = await analyzer.run_agent_loop(profile={}, tool_executor=RecordingExecutor())
    assert proposal.analyzer_descriptor["prompt_version"]


async def test_a_mapping_stays_applicable_after_switching_provider() -> None:
    """ARCHITECTURE §11.5: a mapping produced under one provider must apply
    unchanged under another. It carries no provider reference — the descriptor
    is kept beside it, not inside it."""
    proposal = await FakeAnalyzer().run_agent_loop(profile={}, tool_executor=RecordingExecutor())

    from agentlen.infrastructure.persistence.repositories.mapping_codec import (
        mapping_to_document,
    )

    document = mapping_to_document(proposal.mapping)
    serialised = json.dumps(document).lower()
    for provider in ("anthropic", "openai", "claude", "gpt", "groq", "fake"):
        assert provider not in serialised, f"le mapping mentionne '{provider}'"
