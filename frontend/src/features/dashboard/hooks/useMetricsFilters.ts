import { getRouteApi } from '@tanstack/react-router'

import {
  DATASET_OPTIONS,
  datasetLabel,
  PERIOD_OPTIONS,
  periodLabel,
  searchToDashboardFilters,
  type MetricsPeriod,
  type MetricsSearch,
} from '@/features/dashboard/lib/filters'

const appRoute = getRouteApi('/_app')

export function useMetricsFilters() {
  const search = appRoute.useSearch()
  const navigate = appRoute.useNavigate()
  const filters = searchToDashboardFilters(search)

  const patchSearch = (patch: (prev: MetricsSearch) => MetricsSearch) => {
    void navigate({ search: patch })
  }

  return {
    search,
    filters,
    datasetLabel: datasetLabel(search.data_source_id),
    periodLabel: periodLabel(search.period),
    setDataSourceId: (dataSourceId: number | undefined) => {
      patchSearch((prev) => {
        const next: MetricsSearch = { ...prev }
        if (dataSourceId == null) delete next.data_source_id
        else next.data_source_id = dataSourceId
        return next
      })
    },
    setPeriod: (period: MetricsPeriod | undefined) => {
      patchSearch((prev) => {
        const next: MetricsSearch = { ...prev }
        if (period == null) delete next.period
        else next.period = period
        return next
      })
    },
    datasetOptions: DATASET_OPTIONS,
    periodOptions: PERIOD_OPTIONS,
  }
}
