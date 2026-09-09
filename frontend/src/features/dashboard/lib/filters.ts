import type { DashboardFilters } from '@/features/dashboard/types'

export const METRICS_PERIODS = ['7d', '30d', '90d'] as const
export type MetricsPeriod = (typeof METRICS_PERIODS)[number]

export interface MetricsSearch {
  data_source_id?: number
  period?: MetricsPeriod
}

/** Seed source from `make seed`. No `GET /data-sources` yet — do not invent others. */
export const TRACELAB_SOURCE_ID = 1

export const DATASET_OPTIONS = [
  { id: undefined, label: 'All datasets' },
  { id: TRACELAB_SOURCE_ID, label: 'TraceLab' },
] as const

export const PERIOD_OPTIONS = [
  { id: undefined, label: 'All time' },
  { id: '7d', label: 'Last 7 days' },
  { id: '30d', label: 'Last 30 days' },
  { id: '90d', label: 'Last 90 days' },
] as const

const PERIOD_DAYS: Record<MetricsPeriod, number> = {
  '7d': 7,
  '30d': 30,
  '90d': 90,
}

export function parseMetricsSearch(search: Record<string, unknown>): MetricsSearch {
  const parsed: MetricsSearch = {}
  const id = Number(search.data_source_id)
  if (Number.isInteger(id) && id > 0) parsed.data_source_id = id
  if (typeof search.period === 'string' && METRICS_PERIODS.includes(search.period as MetricsPeriod)) {
    parsed.period = search.period as MetricsPeriod
  }
  return parsed
}

export function datasetLabel(dataSourceId: number | undefined): string {
  const match = DATASET_OPTIONS.find((option) => option.id === dataSourceId)
  if (match) return match.label
  if (dataSourceId == null) return 'All datasets'
  return `Source ${dataSourceId}`
}

export function periodLabel(period: MetricsPeriod | undefined): string {
  return PERIOD_OPTIONS.find((option) => option.id === period)?.label ?? 'All time'
}

export function periodToRange(
  period: MetricsPeriod | undefined,
  now = new Date(),
): Pick<DashboardFilters, 'date_from' | 'date_to'> {
  if (!period) return {}
  const dateTo = new Date(now)
  const dateFrom = new Date(now)
  dateFrom.setUTCDate(dateFrom.getUTCDate() - PERIOD_DAYS[period])
  return {
    date_from: dateFrom.toISOString(),
    date_to: dateTo.toISOString(),
  }
}

export function searchToDashboardFilters(search: MetricsSearch, now = new Date()): DashboardFilters {
  return {
    ...(search.data_source_id != null ? { data_source_id: search.data_source_id } : {}),
    ...periodToRange(search.period, now),
  }
}
