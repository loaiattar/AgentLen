"""AI provider discovery and editable mapping proposals."""

from __future__ import annotations

from fastapi import APIRouter

from agentlen.application.dto.mapping_document import document_to_mapping, mapping_to_document
from agentlen.application.use_cases.propose_mapping import (
    GetMappingProposal,
    PatchMappingProposal,
    ProposeMapping,
    StoredProposal,
)
from agentlen.application.use_cases.refine_mapping import RefineMapping
from agentlen.domain.model.profile import FileProfile
from agentlen.interfaces.http.dependencies import (
    AnalyzerFactoryDep,
    ConversationLimitDep,
    FileProfilerDep,
    ProfileSanitizerDep,
    ProviderStatusDep,
    UnitOfWorkDep,
)
from agentlen.interfaces.http.schemas.ai import (
    ProposalMessageRequest,
    ProposalPatchRequest,
    ProposalRequest,
    ProposalResponse,
)

router = APIRouter(tags=["AI mapping"])


@router.get("/ai/providers")
async def providers(status: ProviderStatusDep) -> dict[str, object]:
    return status


def _response(stored: StoredProposal) -> ProposalResponse:
    proposal = stored.proposal
    return ProposalResponse(
        proposal_id=stored.id,
        analyzer=proposal.analyzer_descriptor,
        mapping=mapping_to_document(proposal.mapping),
        validation=stored.validation,
        rationale=list(proposal.rationale),
        ambiguities=list(proposal.ambiguities),
        unmapped_fields=list(proposal.unmapped_fields),
    )


@router.post("/mappings/proposals", response_model=ProposalResponse)
async def propose(
    body: ProposalRequest,
    uow: UnitOfWorkDep,
    profiler: FileProfilerDep,
    sanitizer: ProfileSanitizerDep,
    analyzer_factory: AnalyzerFactoryDep,
) -> ProposalResponse:
    analyzer = analyzer_factory(body.provider, body.model)
    result = await ProposeMapping(uow, analyzer, profiler, sanitizer).execute(
        file_id=body.file_id,
        data_source_id=body.data_source_id,
        hint=body.hint,
    )
    return _response(result)


@router.get("/mappings/proposals/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(proposal_id: int, uow: UnitOfWorkDep) -> ProposalResponse:
    return _response(await GetMappingProposal(uow).execute(proposal_id))


@router.post("/mappings/proposals/{proposal_id}/messages", response_model=ProposalResponse)
async def refine(
    proposal_id: int,
    body: ProposalMessageRequest,
    uow: UnitOfWorkDep,
    analyzer_factory: AnalyzerFactoryDep,
    max_conversation_turns: ConversationLimitDep,
) -> ProposalResponse:
    current = await GetMappingProposal(uow).execute(proposal_id)
    # Refinement validation only needs the mapping tools; an empty profile does
    # not expose source data and keeps the provider call server-side.
    profile = FileProfile(
        file_id=0, format=current.proposal.mapping.source_format, record_count=0, sampled_records=0
    )
    analyzer = analyzer_factory(
        str(current.proposal.analyzer_descriptor["provider"]),
        str(current.proposal.analyzer_descriptor["model"]),
    )
    return _response(
        await RefineMapping(uow, analyzer, max_conversation_turns=max_conversation_turns).execute(
            proposal_id, body.message, profile
        )
    )


@router.patch("/mappings/proposals/{proposal_id}", response_model=ProposalResponse)
async def patch_proposal(
    proposal_id: int, body: ProposalPatchRequest, uow: UnitOfWorkDep
) -> ProposalResponse:
    document = body.model_dump()
    mapping = document_to_mapping(document)
    return _response(await PatchMappingProposal(uow).execute(proposal_id, mapping))
