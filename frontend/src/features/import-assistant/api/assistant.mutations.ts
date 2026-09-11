import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { assistantKeys } from '@/features/import-assistant/api/assistant.keys'
import type { MappingProposalDocument, ProposalResponse } from '@/features/import-assistant/types'

export function useProposeMappingMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: {
      file_id: number
      data_source_id?: number
      provider?: string | null
      model?: string | null
      hint?: string | null
    }) => apiClient.post<ProposalResponse>('/mappings/proposals', body),
    onSuccess: (data) => {
      queryClient.setQueryData(assistantKeys.proposal(data.proposal_id), data)
    },
  })
}

export function useRefineProposalMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ proposalId, message }: { proposalId: number; message: string }) =>
      apiClient.post<ProposalResponse>(`/mappings/proposals/${proposalId}/messages`, { message }),
    onSuccess: (data) => {
      queryClient.setQueryData(assistantKeys.proposal(data.proposal_id), data)
    },
  })
}

export function usePatchProposalMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ proposalId, mapping }: { proposalId: number; mapping: MappingProposalDocument }) =>
      apiClient.patch<ProposalResponse>(`/mappings/proposals/${proposalId}`, {
        name: mapping.name,
        source_format: mapping.source_format as 'jsonl' | 'csv' | 'parquet',
        entities: mapping.entities,
        mapping_version: mapping.mapping_version ?? '1.0',
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(assistantKeys.proposal(data.proposal_id), data)
    },
  })
}
