import type { DashboardFilters } from '@/features/dashboard/types'

export const dashboardKeys = {
  all: ['dashboard'] as const,
  overview: (filters: DashboardFilters) => [...dashboardKeys.all, 'overview', filters] as const,
  activity: (filters: DashboardFilters) => [...dashboardKeys.all, 'activity', filters] as const,
  tools: (filters: DashboardFilters) => [...dashboardKeys.all, 'tools', filters] as const,
  models: (filters: DashboardFilters) => [...dashboardKeys.all, 'models', filters] as const,
  quality: (filters: DashboardFilters) => [...dashboardKeys.all, 'quality', filters] as const,
  definitions: () => [...dashboardKeys.all, 'definitions'] as const,
}
