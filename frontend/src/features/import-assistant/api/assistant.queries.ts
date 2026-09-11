import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { assistantKeys } from '@/features/import-assistant/api/assistant.keys'
import type { ProposalResponse } from '@/features/import-assistant/types'

export const assistantQueries = {
  proposal: (id: number) =>
    queryOptions({
      queryKey: assistantKeys.proposal(id),
      queryFn: () => apiClient.get<ProposalResponse>(`/mappings/proposals/${id}`),
    }),
}

export function useProposalQuery(id: number | undefined) {
  return useQuery({
    ...assistantQueries.proposal(id ?? 0),
    enabled: id != null && Number.isInteger(id) && id > 0,
  })
}
