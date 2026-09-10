import { Outlet } from '@tanstack/react-router'

import { Shell } from '@/components/ui/Shell'
import { useMetricsFilters } from '@/features/dashboard/hooks/useMetricsFilters'

export function AppLayout() {
  const { datasetLabel, periodLabel, datasetOptions, periodOptions, setDataSourceId, setPeriod } =
    useMetricsFilters()

  return (
    <Shell
      datasetLabel={datasetLabel}
      periodLabel={periodLabel}
      datasetItems={datasetOptions.map((option) => ({
        label: option.label,
        onSelect: () => setDataSourceId(option.id),
      }))}
      periodItems={periodOptions.map((option) => ({
        label: option.label,
        onSelect: () => setPeriod(option.id),
      }))}
    >
      <Outlet />
    </Shell>
  )
}
