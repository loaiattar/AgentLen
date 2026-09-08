import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

import type { ConversationMessage, DraftMappingField } from '@/features/import-assistant/types'

interface ImportAssistantState {
  messages: ConversationMessage[]
  draftName: string
  draftFields: DraftMappingField[]
  addMessage: (message: ConversationMessage) => void
  setDraftName: (name: string) => void
  setDraftFields: (fields: DraftMappingField[]) => void
  updateDraftField: (index: number, field: DraftMappingField) => void
  reset: () => void
}

const initialState = {
  messages: [] as ConversationMessage[],
  draftName: '',
  draftFields: [] as DraftMappingField[],
}

export const useImportAssistantStore = create<ImportAssistantState>()(
  devtools(
    (set) => ({
      ...initialState,
      addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
      setDraftName: (name) => set({ draftName: name }),
      setDraftFields: (fields) => set({ draftFields: fields }),
      updateDraftField: (index, field) =>
        set((state) => ({
          draftFields: state.draftFields.map((current, currentIndex) =>
            currentIndex === index ? field : current,
          ),
        })),
      reset: () => set(initialState),
    }),
    { name: 'ImportAssistantStore', enabled: import.meta.env.DEV },
  ),
)
