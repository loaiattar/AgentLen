import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import type { DashboardFilters } from '@/features/dashboard/types'
import { sessionsKeys } from '@/features/sessions/api/sessions.keys'
import type {
  RawRecordDetail,
  SessionWithCalls,
  SessionsPage,
  TimelineEvent,
} from '@/features/sessions/types'

export function toSessionsQuery(
  filters: DashboardFilters = {},
  limit: number,
  offset: number,
): string {
  const params = new URLSearchParams()

  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === '') continue
    params.set(key, String(value))
  }

  params.set('limit', String(limit))
  params.set('offset', String(offset))
  return `?${params.toString()}`
}

export const sessionsQueries = {
  list: (filters: DashboardFilters = {}, limit: number, offset: number) =>
    queryOptions({
      queryKey: sessionsKeys.list(filters, limit, offset),
      queryFn: () => apiClient.get<SessionsPage>(`/sessions${toSessionsQuery(filters, limit, offset)}`),
    }),
  detail: (id: number) =>
    queryOptions({
      queryKey: sessionsKeys.detail(id),
      queryFn: () => apiClient.get<SessionWithCalls>(`/sessions/${id}`),
    }),
  timeline: (id: number) =>
    queryOptions({
      queryKey: sessionsKeys.timeline(id),
      queryFn: () => apiClient.get<TimelineEvent[]>(`/sessions/${id}/timeline`),
    }),
  record: (id: number) =>
    queryOptions({
      queryKey: sessionsKeys.record(id),
      queryFn: () => apiClient.get<RawRecordDetail>(`/records/${id}`),
    }),
}

export function useSessionsQuery(filters: DashboardFilters = {}, limit: number, offset: number) {
  return useQuery(sessionsQueries.list(filters, limit, offset))
}

export function useSessionQuery(id: number | undefined) {
  return useQuery({
    ...sessionsQueries.detail(id ?? 0),
    enabled: id != null && Number.isInteger(id) && id > 0,
  })
}

export function useSessionTimelineQuery(id: number | undefined) {
  return useQuery({
    ...sessionsQueries.timeline(id ?? 0),
    enabled: id != null && Number.isInteger(id) && id > 0,
  })
}

export function useRawRecordQuery(id: number | undefined) {
  return useQuery({
    ...sessionsQueries.record(id ?? 0),
    enabled: id != null && Number.isInteger(id) && id > 0,
  })
}
