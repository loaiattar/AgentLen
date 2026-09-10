"""Bounded conversational refinement of a stored mapping proposal."""

from __future__ import annotations

import json

from agentlen.application.dto.mapping_document import mapping_to_document
from agentlen.application.ports.structure_analyzer import StructureAnalyzer
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.application.use_cases.propose_mapping import (
    GetMappingProposal,
    MappingValidationTools,
    StoredProposal,
)
from agentlen.domain.model.profile import FileProfile
from agentlen.domain.services import mapping_validator


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
                content=json.dumps(mapping_to_document(refined.mapping), ensure_ascii=False),
            )
            await uow.commit()
        return StoredProposal(proposal_id, refined)
