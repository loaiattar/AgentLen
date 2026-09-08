import { useMutation } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import type { ConversationMessage, DraftMappingField } from '@/features/import-assistant/types'

interface SendMessageInput {
  importId: string
  message: string
}

interface SendMessageResponse {
  reply: ConversationMessage
  suggestedFields?: DraftMappingField[]
}

export function useSendAssistantMessageMutation() {
  return useMutation({
    mutationFn: ({ importId, message }: SendMessageInput) =>
      apiClient.post<SendMessageResponse>(`/import-assistant/${importId}/messages`, { message }),
  })
}
