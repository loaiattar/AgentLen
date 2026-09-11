import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api/client'
import { dashboardKeys } from '@/features/dashboard/api/dashboard.keys'
import { resolvePeriod } from '@/features/dashboard/lib/filters'
import type {
  ActivityPoint,
  DashboardFilters,
  DefinitionsResponse,
  ModelPoint,
  OverviewResponse,
  PointsResponse,
  QualityPoint,
  ToolPoint,
} from '@/features/dashboard/types'

export function toMetricsQuery(filters: DashboardFilters = {}): string {
  const params = new URLSearchParams()

  for (const [key, value] of Object.entries(resolvePeriod(filters))) {
    if (value === undefined || value === null || value === '') continue
    params.set(key, String(value))
  }

  const query = params.toString()
  return query ? `?${query}` : ''
}

export const dashboardQueries = {
  overview: (filters: DashboardFilters = {}) =>
    queryOptions({
      queryKey: dashboardKeys.overview(filters),
      queryFn: () => apiClient.get<OverviewResponse>(`/metrics/overview${toMetricsQuery(filters)}`),
    }),
  activity: (filters: DashboardFilters = {}) =>
    queryOptions({
      queryKey: dashboardKeys.activity(filters),
      queryFn: () =>
        apiClient.get<PointsResponse<ActivityPoint>>(`/metrics/activity${toMetricsQuery(filters)}`),
    }),
  tools: (filters: DashboardFilters = {}) =>
    queryOptions({
      queryKey: dashboardKeys.tools(filters),
      queryFn: () => apiClient.get<PointsResponse<ToolPoint>>(`/metrics/tools${toMetricsQuery(filters)}`),
    }),
  models: (filters: DashboardFilters = {}) =>
    queryOptions({
      queryKey: dashboardKeys.models(filters),
      queryFn: () =>
        apiClient.get<PointsResponse<ModelPoint>>(`/metrics/models${toMetricsQuery(filters)}`),
    }),
  quality: (filters: DashboardFilters = {}) =>
    queryOptions({
      queryKey: dashboardKeys.quality(filters),
      queryFn: () =>
        apiClient.get<PointsResponse<QualityPoint>>(`/metrics/quality${toMetricsQuery(filters)}`),
    }),
  definitions: () =>
    queryOptions({
      queryKey: dashboardKeys.definitions(),
      queryFn: () => apiClient.get<DefinitionsResponse>('/metrics/definitions'),
    }),
}

export function useDashboardOverviewQuery(filters: DashboardFilters = {}) {
  return useQuery(dashboardQueries.overview(filters))
}

export function useDashboardActivityQuery(filters: DashboardFilters = {}) {
  return useQuery(dashboardQueries.activity(filters))
}

export function useDashboardToolsQuery(filters: DashboardFilters = {}) {
  return useQuery(dashboardQueries.tools(filters))
}

export function useDashboardModelsQuery(filters: DashboardFilters = {}) {
  return useQuery(dashboardQueries.models(filters))
}

export function useDashboardQualityQuery(filters: DashboardFilters = {}) {
  return useQuery(dashboardQueries.quality(filters))
}

export function useMetricDefinitionsQuery() {
  return useQuery(dashboardQueries.definitions())
}
