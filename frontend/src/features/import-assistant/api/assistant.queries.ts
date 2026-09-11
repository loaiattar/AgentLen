import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { assistantKeys } from '@/features/import-assistant/api/assistant.keys'
import type {
  AiProvidersResponse,
  FileProfile,
  FileUpload,
  ProposalResponse,
} from '@/features/import-assistant/types'

export const assistantQueries = {
  providers: () =>
    queryOptions({
      queryKey: assistantKeys.providers(),
      queryFn: () => apiClient.get<AiProvidersResponse>('/ai/providers'),
    }),
  file: (id: number) =>
    queryOptions({
      queryKey: assistantKeys.file(id),
      queryFn: () => apiClient.get<FileUpload>(`/files/${id}`),
    }),
  profile: (id: number) =>
    queryOptions({
      queryKey: assistantKeys.profile(id),
      queryFn: () => apiClient.post<FileProfile>(`/files/${id}/profile`),
      staleTime: 5 * 60 * 1000,
      retry: 1,
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

export function useFileQuery(id: number | undefined) {
  return useQuery({
    ...assistantQueries.file(id ?? 0),
    enabled: id != null && Number.isInteger(id) && id > 0,
  })
}

export function useFileProfileQuery(id: number | undefined) {
  return useQuery({
    ...assistantQueries.profile(id ?? 0),
    enabled: id != null && Number.isInteger(id) && id > 0,
  })
}

export function useProposalQuery(id: number | undefined) {
  return useQuery({
    ...assistantQueries.proposal(id ?? 0),
    enabled: id != null && Number.isInteger(id) && id > 0,
  })
}
