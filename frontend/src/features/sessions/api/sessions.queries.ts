import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { sessionsKeys } from '@/features/sessions/api/sessions.keys'
import type { SessionDetail } from '@/features/sessions/types'

function sessionDetailOptions(sessionId: string) {
  return queryOptions({
    queryKey: sessionsKeys.detail(sessionId),
    queryFn: () => apiClient.get<SessionDetail>(`/sessions/${sessionId}`),
    enabled: Boolean(sessionId),
  })
}

export function useSessionDetailQuery(sessionId: string) {
  return useQuery(sessionDetailOptions(sessionId))
}
