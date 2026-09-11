"""Bounded conversational refinement of a stored mapping proposal."""

from __future__ import annotations

from agentlen.application.ports.structure_analyzer import StructureAnalyzer
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.application.use_cases.propose_mapping import (
    GetMappingProposal,
    MappingValidationTools,
    StoredProposal,
)
from agentlen.domain.model.mapping import Mapping
from agentlen.domain.model.profile import FileProfile
from agentlen.domain.services import mapping_validator


def _summarize(mapping: Mapping) -> str:
    """What the assistant turn stores — a line, not the whole document.

    These rows exist for one reason: `RefineMapping` reads the last
    `2 * max_turns` of them back and the adapter injects them into the next
    refinement prompt. Storing `mapping_to_document(...)` there put a complete
    mapping in every assistant turn, so by the tenth round the prompt carried
    ten of them, double-encoded, on top of the current mapping — tens to
    hundreds of KB, and eventually a provider context-length error. The mapping
    itself is not lost: `mapping_proposals.update` persists it in the same
    transaction, and nothing but the prompt ever reads these rows.
    """
    entities = ", ".join(entity.target for entity in mapping.entities) or "aucune"
    rules = sum(len(entity.fields) for entity in mapping.entities)
    return f"Proposition mise à jour : {rules} règle(s) sur {entities}."


class RefineMapping:
    def __init__(
        self,
        uow: UnitOfWork,
        analyzer: StructureAnalyzer,
        *,
        max_conversation_turns: int = 10,
    ) -> None:
        if max_conversation_turns < 1:
            raise ValueError("max_conversation_turns must be positive")
        self._uow = uow
        self._analyzer = analyzer
        self._max_turns = max_conversation_turns

    async def execute(self, proposal_id: int, message: str, profile: FileProfile) -> StoredProposal:
        current = await GetMappingProposal(self._uow).execute(proposal_id)
        async with self._uow as uow:
            history = await uow.mapping_proposals.list_messages(
                proposal_id, limit=2 * self._max_turns
            )
        refined = await self._analyzer.refine(
            current.proposal,
            message,
            MappingValidationTools(profile),
            tuple(history),
        )
        mapping_validator.validate(refined.mapping)
        async with self._uow as uow:
            await uow.mapping_proposals.add_message(proposal_id, role="user", content=message)
            await uow.mapping_proposals.update(proposal_id, refined)
            await uow.mapping_proposals.add_message(
                proposal_id,
                role="assistant",
                content=_summarize(refined.mapping),
            )
            await uow.commit()
        return StoredProposal(proposal_id, refined)
