import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { assistantKeys } from '@/features/import-assistant/api/assistant.keys'
import type { AiProvidersResponse, ProposalResponse } from '@/features/import-assistant/types'

export const assistantQueries = {
  providers: () =>
    queryOptions({
      queryKey: assistantKeys.providers(),
      queryFn: () => apiClient.get<AiProvidersResponse>('/ai/providers'),
    }),
  proposal: (id: number) =>
    queryOptions({
      queryKey: assistantKeys.proposal(id),
      queryFn: () => apiClient.get<ProposalResponse>(`/mappings/proposals/${id}`),
    }),
}

export function useAiProvidersQuery() {
  return useQuery(assistantQueries.providers())
}

export function useProposalQuery(id: number | undefined) {
  return useQuery({
    ...assistantQueries.proposal(id ?? 0),
    enabled: id != null && Number.isInteger(id) && id > 0,
  })
}
