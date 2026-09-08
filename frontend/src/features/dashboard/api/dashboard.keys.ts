import type { DashboardFilters } from '@/features/dashboard/types'

export const dashboardKeys = {
  all: ['dashboard'] as const,
  metrics: (filters: DashboardFilters) => [...dashboardKeys.all, 'metrics', filters] as const,
}
