import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { systemKeys } from '@/features/system/api/system.keys'
import type { AiProvidersResponse, ReadinessResponse } from '@/features/system/types'

/** How often the shell re-checks readiness, so the status never outlives the server state for long. */
const READINESS_REFETCH_MS = 60 * 1000

export const systemQueries = {
  aiProviders: () =>
    queryOptions({
      queryKey: systemKeys.aiProviders(),
      queryFn: () => apiClient.get<AiProvidersResponse>('/ai/providers'),
    }),
  readiness: () =>
    queryOptions({
      queryKey: systemKeys.readiness(),
      queryFn: () => apiClient.get<ReadinessResponse>('/health/ready'),
      refetchInterval: READINESS_REFETCH_MS,
      // A 503 is an answer, not a transient failure: show it at once instead of retrying.
      retry: false,
    }),
}

export function useAiProvidersQuery() {
  return useQuery(systemQueries.aiProviders())
}

export function useReadinessQuery() {
  return useQuery(systemQueries.readiness())
}
