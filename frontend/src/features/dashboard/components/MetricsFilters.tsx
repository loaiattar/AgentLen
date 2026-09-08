import { Button } from '@/components/atoms/Button'
import type { DashboardFilters } from '@/features/dashboard/types'

const PERIODS: DashboardFilters['period'][] = ['24h', '7d', '30d']

export interface MetricsFiltersProps {
  filters: DashboardFilters
  onChange: (filters: DashboardFilters) => void
}

export function MetricsFilters({ filters, onChange }: MetricsFiltersProps) {
  return (
    <div className="flex items-center gap-2">
      {PERIODS.map((period) => (
        <Button
          key={period}
          size="sm"
          variant={filters.period === period ? 'default' : 'outline'}
          onClick={() => onChange({ ...filters, period })}
        >
          {period}
        </Button>
      ))}
    </div>
  )
}
