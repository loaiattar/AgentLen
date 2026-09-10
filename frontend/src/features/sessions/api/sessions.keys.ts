import type { DashboardFilters } from '@/features/dashboard/types'

export const sessionsKeys = {
  all: ['sessions'] as const,
  lists: () => [...sessionsKeys.all, 'list'] as const,
  list: (filters: DashboardFilters, limit: number, offset: number) =>
    [...sessionsKeys.lists(), { filters, limit, offset }] as const,
  details: () => [...sessionsKeys.all, 'detail'] as const,
  detail: (id: number) => [...sessionsKeys.details(), id] as const,
  timeline: (id: number) => [...sessionsKeys.all, 'timeline', id] as const,
  record: (id: number) => [...sessionsKeys.all, 'record', id] as const,
}
