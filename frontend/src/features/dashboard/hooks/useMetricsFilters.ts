import { getRouteApi, useNavigate } from '@tanstack/react-router'

import {
  datasetLabel,
  datasetOptions,
  EXPLORATION_KEYS,
  PERIOD_OPTIONS,
  periodLabel,
  readDateRange,
  searchToDashboardFilters,
  withoutIgnoredDates,
  withoutSearchKeys,
  type ExplorationKey,
  type MetricsPeriod,
  type MetricsSearch,
} from '@/features/dashboard/lib/filters'
import { useDataSourcesQuery } from '@/features/imports/api/imports.queries'

const appRoute = getRouteApi('/_app')

export function useMetricsFilters() {
  const search = appRoute.useSearch()
  const navigate = useNavigate()
  const sources = useDataSourcesQuery()
  // Every page of `GET /data-sources` is loaded (#192): the names are its `items`.
  const sourceList = sources.data?.items
  const filters = searchToDashboardFilters(search)

  const patchSearch = (patch: (prev: MetricsSearch) => MetricsSearch) => {
    void navigate({ to: '.', search: patch })
  }

  return {
    search,
    filters,
    sources: sourceList ?? [],
    datasetLabel: datasetLabel(search.data_source_id, sourceList),
    periodLabel: periodLabel(search),
    // Dates stay raw in `search` (see `parseMetricsSearch`), so the page can say what it ignores.
    ignoredDates: readDateRange(search).ignored,
    setDataSourceId: (dataSourceId: number | undefined) => {
      patchSearch((prev) => {
        const next: MetricsSearch = { ...prev }
        delete next.offset
        delete next.mapping_id
        if (dataSourceId == null) delete next.data_source_id
        else next.data_source_id = dataSourceId
        return next
      })
    },
    setPeriod: (period: MetricsPeriod | undefined) => {
      patchSearch((prev) => {
        const next: MetricsSearch = { ...prev }
        delete next.date_from
        delete next.date_to
        delete next.offset
        if (period == null) delete next.period
        else next.period = period
        return next
      })
    },
    removeFilter: (key: ExplorationKey) => patchSearch((prev) => withoutSearchKeys(prev, [key])),
    clearExploration: () => patchSearch((prev) => withoutSearchKeys(prev, EXPLORATION_KEYS)),
    dropIgnoredDates: () => patchSearch(withoutIgnoredDates),
    datasetOptions: datasetOptions({ data: sourceList, isPending: sources.isPending, isError: sources.isError }),
    periodOptions: PERIOD_OPTIONS,
  }
}
