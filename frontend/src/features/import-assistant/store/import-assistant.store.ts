import { create } from 'zustand'

import type { ChatTurn, MappingDocument } from '@/features/import-assistant/types'

interface AssistantDraftState {
  composer: string
  turns: ChatTurn[]
  mappingDraft: MappingDocument | null
  draftProposalId: number | null
  acceptedMappingId: number | null
  setComposer: (value: string) => void
  pushTurn: (turn: ChatTurn) => void
  setMappingDraft: (proposalId: number, mapping: MappingDocument) => void
  clearMappingDraft: () => void
  setAcceptedMappingId: (id: number | null) => void
  syncProposal: (proposalId: number | undefined) => void
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
  syncProposal: (proposalId) => {
    if (proposalId === get().draftProposalId) return
    set({
      composer: '',
      turns: [],
      mappingDraft: null,
      draftProposalId: proposalId ?? null,
      acceptedMappingId: null,
    })
  },
}))
