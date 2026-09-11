import { create } from 'zustand'

import type { ChatTurn, MappingProposalDocument } from '@/features/import-assistant/types'

interface AssistantDraftState {
  composer: string
  turns: ChatTurn[]
  mappingDraft: MappingProposalDocument | null
  draftProposalId: number | null
  acceptedMappingId: number | null
  setComposer: (value: string) => void
  pushTurn: (turn: ChatTurn) => void
  setMappingDraft: (proposalId: number, mapping: MappingProposalDocument) => void
  clearMappingDraft: () => void
  setAcceptedMappingId: (id: number | null) => void
  syncProposal: (proposalId: number | undefined, mappingId: number | undefined) => void
}

export const useImportAssistantStore = create<AssistantDraftState>((set, get) => ({
  composer: '',
  turns: [],
  mappingDraft: null,
  draftProposalId: null,
  acceptedMappingId: null,
  setComposer: (composer) => set({ composer }),
  pushTurn: (turn) => set({ turns: [...get().turns, turn] }),
  setMappingDraft: (draftProposalId, mappingDraft) => set({ draftProposalId, mappingDraft }),
  clearMappingDraft: () => set({ mappingDraft: null }),
  setAcceptedMappingId: (acceptedMappingId) => set({ acceptedMappingId }),
  /**
   * The URL owns `mapping_id`, this store only mirrors it. Seeding
   * `acceptedMappingId` from the search params is what makes a reload — or a
   * shared link — resume on the accepted mapping instead of offering to accept
   * the same proposal a second time; dropping it when the id leaves the URL
   * (a data source change clears `mapping_id`) is what stops the studio from
   * advertising a mapping the pipeline no longer carries.
   */
  syncProposal: (proposalId, mappingId) => {
    const state = get()
    const nextMappingId = mappingId ?? null
    if (proposalId !== state.draftProposalId) {
      set({
        composer: '',
        turns: [],
        mappingDraft: null,
        draftProposalId: proposalId ?? null,
        acceptedMappingId: nextMappingId,
      })
      return
    }
    if (nextMappingId !== state.acceptedMappingId) set({ acceptedMappingId: nextMappingId })
  },
}))
