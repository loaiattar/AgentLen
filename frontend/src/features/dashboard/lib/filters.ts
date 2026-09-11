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
  file_id?: number
  proposal_id?: number
  mapping_id?: number
}

/** Filters a drill-down adds on top of the header's dataset and period. */
export const DRILL_DOWN_KEYS = ['agent_id', 'model_id', 'tool_id', 'import_run_id', 'date_from', 'date_to'] as const
export const EXPLORATION_KEYS = ['status', ...DRILL_DOWN_KEYS] as const
export type ExplorationKey = (typeof EXPLORATION_KEYS)[number]

/** The part of `GET /data-sources` the filters need. */
export interface SourceName {
  id: number
  name: string
}

export interface DatasetOption {
  id: number | undefined
  label: string
  disabled?: boolean
}

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

const INSTANT_PATTERN = /^\d{4}-\d{2}-\d{2}(T([01]\d|2[0-3]):[0-5]\d(:[0-5]\d(\.\d{1,6})?)?(Z|[+-]\d{2}:\d{2})?)?$/

/**
 * Epoch milliseconds of an instant the API reads, else `undefined`.
 *
 * `Date.parse` alone is too lenient: it reads "September 1, 2026" and rolls
 * 2026-02-30 over to March, and the API answers 400 to both. A value without
 * offset is read as UTC, the calendar the API groups days by.
 */
export function parseInstant(value: unknown): number | undefined {
  if (typeof value !== 'string') return undefined
  const match = INSTANT_PATTERN.exec(value)
  if (!match) return undefined
  const day = value.slice(0, 10)
  const calendar = Date.parse(`${day}T00:00:00Z`)
  if (Number.isNaN(calendar) || new Date(calendar).toISOString().slice(0, 10) !== day) return undefined
  const time = Date.parse(match[1] == null ? `${day}T00:00:00Z` : match[5] == null ? `${value}Z` : value)
  return Number.isNaN(time) ? undefined : time
}

const DATE_NAMES = { date_from: 'start date', date_to: 'end date' } as const

/**
 * The URL's dates the API can use, and why the others are ignored — an
 * unreadable date, or a range that ends before it starts.
 */
export function readDateRange(search: { date_from?: unknown; date_to?: unknown }): {
  dates: Pick<MetricsSearch, 'date_from' | 'date_to'>
  ignored: string[]
} {
  const dates: Pick<MetricsSearch, 'date_from' | 'date_to'> = {}
  const ignored: string[] = []
  for (const key of ['date_from', 'date_to'] as const) {
    const value = search[key]
    if (value == null || value === '') continue
    if (parseInstant(value) == null) ignored.push(`The ${DATE_NAMES[key]} “${String(value)}” is not a date: it is ignored.`)
    else dates[key] = value as string
  }
  const from = parseInstant(dates.date_from)
  const to = parseInstant(dates.date_to)
  if (from != null && to != null && from > to) {
    return { dates: {}, ignored: [...ignored, 'The date range ends before it starts: both dates are ignored.'] }
  }
  return { dates, ignored }
}

export function parseMetricsSearch(search: Record<string, unknown>): MetricsSearch {
  const parsed: MetricsSearch = {}
  const dataSourceId = parseIntParam(search.data_source_id, { min: 1 })
  const agentId = parseIntParam(search.agent_id, { min: 1 })
  const modelId = parseIntParam(search.model_id, { min: 1 })
  const toolId = parseIntParam(search.tool_id, { min: 1 })
  const importRunId = parseIntParam(search.import_run_id, { min: 1 })
  const fileId = parseIntParam(search.file_id, { min: 1 })
  const proposalId = parseIntParam(search.proposal_id, { min: 1 })
  const mappingId = parseIntParam(search.mapping_id, { min: 1 })
  const limit = parseIntParam(search.limit, { min: 1, max: SESSION_PAGE_SIZE_MAX })
  const offset = parseIntParam(search.offset, { min: 0 })

  if (dataSourceId != null) parsed.data_source_id = dataSourceId
  if (agentId != null) parsed.agent_id = agentId
  if (modelId != null) parsed.model_id = modelId
  if (toolId != null) parsed.tool_id = toolId
  if (importRunId != null) parsed.import_run_id = importRunId
  if (fileId != null) parsed.file_id = fileId
  if (proposalId != null) parsed.proposal_id = proposalId
  if (mappingId != null) parsed.mapping_id = mappingId
  Object.assign(parsed, readDateRange(search).dates)
  if (typeof search.status === 'string' && SESSION_STATUSES.includes(search.status as SessionStatus)) {
    parsed.status = search.status as SessionStatus
  }
  if (typeof search.period === 'string' && METRICS_PERIODS.includes(search.period as MetricsPeriod)) {
    parsed.period = search.period as MetricsPeriod
  }
  if (limit != null) parsed.limit = limit
  if (offset != null && offset > 0) parsed.offset = offset
  // The router spreads the raw URL under what `validateSearch` returns, so a
  // key left out keeps its raw value in `useSearch()`: reset it. Dates are the
  // exception — kept in the link so the page can say why it ignores them, and
  // read only through `readDateRange`.
  for (const key of METRICS_SEARCH_KEYS) {
    if (!(key in parsed) && key in search) parsed[key] = undefined
  }
  return parsed
}

const METRICS_SEARCH_KEYS: readonly (keyof MetricsSearch)[] = [
  'data_source_id',
  'agent_id',
  'model_id',
  'tool_id',
  'import_run_id',
  'status',
  'period',
  'limit',
  'offset',
  'file_id',
  'proposal_id',
  'mapping_id',
]

/** Replay a chart point's `filters` onto `/sessions` with no translation. */
export function toSessionSearch(filters: Record<string, unknown>): MetricsSearch {
  return parseMetricsSearch(filters)
}

/**
 * Drop filters and go back to the first page. A dropped date takes the period
 * with it: hidden while dates override it, it would otherwise come back unseen.
 */
export function withoutSearchKeys(prev: MetricsSearch, keys: readonly (keyof MetricsSearch)[]): MetricsSearch {
  const next: MetricsSearch = { ...prev }
  for (const key of keys) {
    if ((key === 'date_from' || key === 'date_to') && prev[key] != null) delete next.period
    delete next[key]
  }
  delete next.offset
  return next
}

/** Take the dates validation ignored out of the link, and keep the valid ones. */
export function withoutIgnoredDates(prev: MetricsSearch): MetricsSearch {
  const next: MetricsSearch = { ...prev }
  delete next.date_from
  delete next.date_to
  return { ...next, ...readDateRange(prev).dates }
}

/** The dataset menu: every declared source, and a disabled line saying why there are none. */
export function datasetOptions(sources: {
  data?: readonly SourceName[]
  isPending: boolean
  isError: boolean
}): DatasetOption[] {
  return [
    { id: undefined, label: 'All datasets' },
    ...(sources.data ?? []).map((source) => ({ id: source.id, label: source.name })),
    ...(sources.isPending ? [{ id: undefined, label: 'Loading sources…', disabled: true }] : []),
    ...(sources.isError ? [{ id: undefined, label: 'Sources unavailable', disabled: true }] : []),
  ]
}

export function datasetLabel(dataSourceId: number | undefined, sources: readonly SourceName[] = []): string {
  if (dataSourceId == null) return 'All datasets'
  return sources.find((source) => source.id === dataSourceId)?.name ?? `Source ${dataSourceId}`
}

export function periodLabel(search: Pick<MetricsSearch, 'period' | 'date_from' | 'date_to'>): string {
  // Dates override the period (`searchToDashboardFilters`): naming the period would be untrue.
  const { dates } = readDateRange(search)
  if (dates.date_from || dates.date_to) return 'Custom range'
  return PERIOD_OPTIONS.find((option) => option.id === search.period)?.label ?? 'All time'
}

const FILTER_LABELS: Record<ExplorationKey, string> = {
  status: 'Status',
  agent_id: 'Agent',
  model_id: 'Model',
  tool_id: 'Tool',
  import_run_id: 'Import',
  date_from: 'From',
  date_to: 'To',
}

// UTC, like the day buckets a date drill-down comes from.
const chipInstantFormat = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZone: 'UTC',
})

export function filterChipLabel(key: ExplorationKey, value: string | number): string {
  const time = key === 'date_from' || key === 'date_to' ? parseInstant(value) : undefined
  return `${FILTER_LABELS[key]} ${time == null ? String(value) : `${chipInstantFormat.format(time)} UTC`}`
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

/**
 * The filters the URL describes — identical for as long as the URL is.
 *
 * A period stays a period here and only becomes dates when a request is sent
 * (`resolvePeriod`). Resolving it at render time put `new Date()`, to the
 * millisecond, into every query key: each render made a new key, each response
 * re-rendered, and the dashboard refetched in a loop (#122).
 */
export function searchToDashboardFilters(search: MetricsSearch): DashboardFilters {
  const valid = readDateRange(search).dates
  const hasDates = Boolean(valid.date_from || valid.date_to)
  const dates = hasDates
    ? valid
    : search.period
      ? { period: search.period }
      : {}

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

/**
 * The query parameters the API expects: a period becomes a date range, computed
 * when the request leaves — never earlier, so it never reaches a query key.
 */
export function resolvePeriod(
  filters: DashboardFilters,
  now = new Date(),
): Omit<DashboardFilters, 'period'> {
  const { period, ...rest } = filters
  if (!period || rest.date_from || rest.date_to) return rest
  return { ...rest, ...periodToRange(period, now) }
}
