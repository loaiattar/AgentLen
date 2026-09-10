import type { DashboardFilters } from '@/features/dashboard/types'

export const METRICS_PERIODS = ['7d', '30d', '90d'] as const
export type MetricsPeriod = (typeof METRICS_PERIODS)[number]

export const SESSION_STATUSES = ['completed', 'error', 'aborted', 'unknown'] as const
export type SessionStatus = (typeof SESSION_STATUSES)[number]

export const SESSION_PAGE_SIZE = 50
export const SESSION_PAGE_SIZE_MAX = 200

export interface MetricsSearch {
  data_source_id?: number
  agent_id?: number
  model_id?: number
  tool_id?: number
  import_run_id?: number
  date_from?: string
  date_to?: string
  status?: SessionStatus
  period?: MetricsPeriod
  limit?: number
  offset?: number
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

function parseIntParam(value: unknown, { min, max }: { min: number; max?: number }): number | undefined {
  const parsed = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : Number.NaN
  if (!Number.isInteger(parsed) || parsed < min) return undefined
  if (max != null && parsed > max) return undefined
  return parsed
}

export function parseMetricsSearch(search: Record<string, unknown>): MetricsSearch {
  const parsed: MetricsSearch = {}
  const dataSourceId = parseIntParam(search.data_source_id, { min: 1 })
  const agentId = parseIntParam(search.agent_id, { min: 1 })
  const modelId = parseIntParam(search.model_id, { min: 1 })
  const toolId = parseIntParam(search.tool_id, { min: 1 })
  const importRunId = parseIntParam(search.import_run_id, { min: 1 })
  const limit = parseIntParam(search.limit, { min: 1, max: SESSION_PAGE_SIZE_MAX })
  const offset = parseIntParam(search.offset, { min: 0 })

  if (dataSourceId != null) parsed.data_source_id = dataSourceId
  if (agentId != null) parsed.agent_id = agentId
  if (modelId != null) parsed.model_id = modelId
  if (toolId != null) parsed.tool_id = toolId
  if (importRunId != null) parsed.import_run_id = importRunId
  if (typeof search.date_from === 'string' && search.date_from.length > 0) parsed.date_from = search.date_from
  if (typeof search.date_to === 'string' && search.date_to.length > 0) parsed.date_to = search.date_to
  if (typeof search.status === 'string' && SESSION_STATUSES.includes(search.status as SessionStatus)) {
    parsed.status = search.status as SessionStatus
  }
  if (typeof search.period === 'string' && METRICS_PERIODS.includes(search.period as MetricsPeriod)) {
    parsed.period = search.period as MetricsPeriod
  }
  if (limit != null) parsed.limit = limit
  if (offset != null && offset > 0) parsed.offset = offset
  return parsed
}

/** Replay a chart point's `filters` onto `/sessions` with no translation. */
export function toSessionSearch(filters: Record<string, unknown>): MetricsSearch {
  return parseMetricsSearch(filters)
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
  const dates =
    search.date_from || search.date_to
      ? {
          ...(search.date_from ? { date_from: search.date_from } : {}),
          ...(search.date_to ? { date_to: search.date_to } : {}),
        }
      : periodToRange(search.period, now)

  return {
    ...(search.data_source_id != null ? { data_source_id: search.data_source_id } : {}),
    ...(search.agent_id != null ? { agent_id: search.agent_id } : {}),
    ...(search.model_id != null ? { model_id: search.model_id } : {}),
    ...(search.tool_id != null ? { tool_id: search.tool_id } : {}),
    ...(search.import_run_id != null ? { import_run_id: search.import_run_id } : {}),
    ...(search.status ? { status: search.status } : {}),
    ...dates,
  }
}
