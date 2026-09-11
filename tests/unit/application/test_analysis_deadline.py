"""The overall deadline on a proposal and on a refinement (#191)."""

from __future__ import annotations

import asyncio

import pytest

from agentlen.application.errors import AnalyzerError, AnalyzerTimeoutError
from agentlen.application.use_cases.analysis_deadline import DeadlineBoundAnalyzer
from agentlen.application.use_cases.propose_mapping import ProposeMapping
from agentlen.application.use_cases.refine_mapping import RefineMapping
from agentlen.domain.model.mapping import MappingProposal
from agentlen.domain.model.profile import FileProfile
from agentlen.infrastructure.ai.sanitizer import ProfileExampleSanitizer
from tests.fakes.repositories import InMemoryUnitOfWork
from tests.unit.application.test_mapping_use_cases import (
    FakeProfiler,
    RecordingFakeAnalyzer,
    stored_file,
    valid_mapping,
)

PROFILE = FileProfile(file_id=1, format="jsonl", record_count=0, sampled_records=0)


class SlowAnalyzer(RecordingFakeAnalyzer):
    """A provider that never answers in time, and notices being cancelled."""

    cancelled = False

    async def _hang(self) -> None:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    async def run_agent_loop(self, profile, tool_executor, hint=None):
        await self._hang()

    async def refine(self, proposal, user_message, tool_executor, history=()):
        await self._hang()


async def test_a_slow_proposal_stops_at_the_deadline_and_saves_nothing() -> None:
    uow = InMemoryUnitOfWork()
    file_id = await stored_file(uow)
    slow = SlowAnalyzer()
    use_case = ProposeMapping(
        uow, DeadlineBoundAnalyzer(slow, 0.05), FakeProfiler(), ProfileExampleSanitizer()
    )

    with pytest.raises(AnalyzerTimeoutError) as exc:
        await use_case.execute(file_id=file_id, data_source_id=None)

    assert (exc.value.code, exc.value.details) == (
        "ANALYZER_TIMEOUT",
        {"total_timeout_seconds": 0.05},
    )
    assert isinstance(exc.value, AnalyzerError)
    assert slow.cancelled, "the analysis must be cancelled, not left running"
    assert uow._store.mapping_proposals == {}


async def test_a_slow_refinement_stops_at_the_deadline_and_records_no_turn() -> None:
    uow = InMemoryUnitOfWork()
    slow = SlowAnalyzer()
    proposal = MappingProposal(valid_mapping(), (), (), (), slow.descriptor)
    async with uow as transaction:
        proposal_id = await transaction.mapping_proposals.save(proposal, file_upload_id=1)
        await transaction.commit()

    with pytest.raises(AnalyzerTimeoutError):
        await RefineMapping(uow, DeadlineBoundAnalyzer(slow, 0.05)).execute(
            proposal_id, "corrige", PROFILE
        )

    assert slow.cancelled
    assert uow._store.proposal_messages == []


async def test_an_analysis_within_the_deadline_is_unchanged() -> None:
    uow = InMemoryUnitOfWork()
    inner = RecordingFakeAnalyzer()
    use_case = ProposeMapping(
        uow, DeadlineBoundAnalyzer(inner, 5), FakeProfiler(), ProfileExampleSanitizer()
    )

    result = await use_case.execute(file_id=await stored_file(uow), data_source_id=None)

    assert result.proposal.analyzer_descriptor == inner.descriptor


async def test_a_timeout_raised_by_the_analysis_itself_is_not_the_deadline() -> None:
    class Raising(RecordingFakeAnalyzer):
        async def run_agent_loop(self, profile, tool_executor, hint=None):
            raise TimeoutError("inner")

    with pytest.raises(TimeoutError, match="inner") as exc:
        await DeadlineBoundAnalyzer(Raising(), 5).run_agent_loop(PROFILE, None)  # type: ignore[arg-type]

    assert not isinstance(exc.value, AnalyzerTimeoutError)
