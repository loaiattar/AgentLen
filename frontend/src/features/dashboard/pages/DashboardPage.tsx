import { getRouteApi } from '@tanstack/react-router'

import { DashboardTemplate } from '@/components/templates/DashboardTemplate'
import { useDashboardMetricsQuery } from '@/features/dashboard/api/dashboard.queries'
import { MetricCard } from '@/features/dashboard/components/MetricCard'
import { MetricsFilters } from '@/features/dashboard/components/MetricsFilters'

const routeApi = getRouteApi('/_app/')

export function DashboardPage() {
  const filters = routeApi.useSearch()
  const navigate = routeApi.useNavigate()
  const { data, isLoading, isError } = useDashboardMetricsQuery(filters)

  return (
    <DashboardTemplate
      filters={
        <MetricsFilters
          filters={filters}
          onChange={(next) => navigate({ search: next })}
        />
      }
      content={
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <MetricCard label="Sessions" value={isLoading ? '…' : isError ? '—' : String(data?.totalSessions ?? 0)} />
          <MetricCard label="Appels" value={isLoading ? '…' : isError ? '—' : String(data?.totalCalls ?? 0)} />
          <MetricCard
            label="Taux d'erreur"
            value={isLoading ? '…' : isError ? '—' : `${((data?.errorRate ?? 0) * 100).toFixed(1)}%`}
          />
          <MetricCard
            label="Latence moyenne"
            value={isLoading ? '…' : isError ? '—' : `${data?.averageLatencyMs ?? 0} ms`}
          />
        </div>
      }
    />
  )
}
