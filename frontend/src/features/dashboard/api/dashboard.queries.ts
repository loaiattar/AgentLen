import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { dashboardKeys } from '@/features/dashboard/api/dashboard.keys'
import type { DashboardFilters, DashboardMetrics } from '@/features/dashboard/types'

function buildSearchParams(filters: DashboardFilters) {
  const params = new URLSearchParams()
  if (filters.source) params.set('source', filters.source)
  if (filters.agent) params.set('agent', filters.agent)
  if (filters.model) params.set('model', filters.model)
  if (filters.period) params.set('period', filters.period)
  return params.toString()
}

function dashboardMetricsOptions(filters: DashboardFilters) {
  return queryOptions({
    queryKey: dashboardKeys.metrics(filters),
    queryFn: () => apiClient.get<DashboardMetrics>(`/dashboard/metrics?${buildSearchParams(filters)}`),
  })
}

export function useDashboardMetricsQuery(filters: DashboardFilters) {
  return useQuery(dashboardMetricsOptions(filters))
}
