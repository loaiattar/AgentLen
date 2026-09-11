import { datasetLabel } from '@/features/dashboard/lib/filters'
import type {
  ActivityPoint,
  DashboardFilters,
  Metric,
  MetricDefinition,
  ModelPoint,
  QualityPoint,
  ToolPoint,
} from '@/features/dashboard/types'

export const MISSING_VALUE = '—'

const numberFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 })
const compactFormat = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1,
})

export function formatDay(value: string | null | undefined): string {
  if (!value) return MISSING_VALUE
  const date = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short' }).format(date)
}

export function getMetric(metrics: Metric[] | undefined, key: string): Metric | undefined {
  return metrics?.find((metric) => metric.key === key)
}

export function getDefinition(
  definitions: MetricDefinition[] | undefined,
  key: string,
): MetricDefinition | undefined {
  return definitions?.find((definition) => definition.key === key)
}

export function formatCount(value: number | null | undefined): string {
  if (value == null) return MISSING_VALUE
  return numberFormat.format(value)
}

export function formatTokens(value: number | null | undefined): string {
  if (value == null) return MISSING_VALUE
  return compactFormat.format(value)
}

export function formatDurationMs(value: number | null | undefined): string {
  if (value == null) return MISSING_VALUE
  const totalSeconds = Math.round(value / 1000)
  if (totalSeconds < 60) return `${totalSeconds}s`
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return seconds === 0 ? `${minutes}m` : `${minutes}m ${seconds}s`
}

export function formatRatio(value: number | null | undefined): string {
  if (value == null) return MISSING_VALUE
  return `${numberFormat.format(value * 100)}%`
}

export function coverageHint(metric: Metric | undefined): string | undefined {
  if (!metric) return undefined
  if (metric.warning) return metric.warning
  if (metric.coverage.total === 0 || metric.coverage.ratio >= 1) return undefined
  return `Based on ${metric.coverage.present} of ${metric.coverage.total}`
}

export function collectDashboardWarnings(
  metrics: Metric[],
  envelopes: Array<{ warnings?: string[] } | undefined>,
): string[] {
  const seen = new Set<string>()
  const warnings: string[] = []

  const push = (warning: string | null | undefined) => {
    if (!warning || seen.has(warning)) return
    seen.add(warning)
    warnings.push(warning)
  }

  for (const metric of metrics) push(metric.warning)
  for (const envelope of envelopes) {
    for (const warning of envelope?.warnings ?? []) push(warning)
  }

  return warnings
}

const CHART_TONES = ['cyan', 'blue', 'mint', 'magenta'] as const

export interface DayBucket {
  /** `YYYY-MM-DD`, UTC — the calendar the API groups activity by. */
  day: string
  /** A day with no activity point had no session: a true 0. */
  sessions: number
  /** Known tokens. `null` when the day had sessions but none reported tokens. */
  tokens: number | null
  /** Replayable on `/sessions`; `null` when there is no session to open. */
  filters: Record<string, unknown> | null
}

const DAY_MS = 24 * 60 * 60 * 1000

/** Past this span a requested range is not drawn day by day; the data's own span is. */
export const MAX_RANGE_DAYS = 3 * 366

function toUtcDay(value: string | undefined, { endOfRange = false } = {}): string | undefined {
  if (!value) return undefined
  const time = Date.parse(value)
  if (Number.isNaN(time)) return undefined
  // A range ending exactly at midnight (a day drill-down) does not cover the next day.
  const adjusted = endOfRange && time % DAY_MS === 0 ? time - DAY_MS : time
  return new Date(adjusted).toISOString().slice(0, 10)
}

function daysBetween(first: string, last: string): number {
  return Math.round((Date.parse(`${last}T00:00:00Z`) - Date.parse(`${first}T00:00:00Z`)) / DAY_MS)
}

function dayFilters(points: ActivityPoint[]): Record<string, unknown> | null {
  const [head, ...rest] = points
  if (!head) return null
  const filters = { ...head.filters }
  // One point per source: a day spanning several sources opens all of them.
  if (rest.some((point) => point.filters.data_source_id !== head.filters.data_source_id)) {
    delete filters.data_source_id
  }
  return filters
}

/**
 * One bucket per calendar day over the displayed range, days without activity
 * included, so spacing on the chart is proportional to time. The range is the
 * requested one when it is known, widened to the data if needed.
 */
export function dailySeries(
  points: ActivityPoint[],
  range: Pick<DashboardFilters, 'date_from' | 'date_to'> = {},
): DayBucket[] {
  const byDay = new Map<string, ActivityPoint[]>()
  for (const point of points) byDay.set(point.day, [...(byDay.get(point.day) ?? []), point])

  const dataDays = [...byDay.keys()].sort()
  const dataFirst = dataDays[0]
  const dataLast = dataDays.at(-1)
  if (!dataFirst || !dataLast) return []

  const from = toUtcDay(range.date_from)
  const to = toUtcDay(range.date_to, { endOfRange: true })
  let first = from && from < dataFirst ? from : dataFirst
  let last = to && to > dataLast ? to : dataLast
  if (daysBetween(first, last) > MAX_RANGE_DAYS) {
    first = dataFirst
    last = dataLast
  }

  const start = Date.parse(`${first}T00:00:00Z`)
  return Array.from({ length: daysBetween(first, last) + 1 }, (_, offset) => {
    const day = new Date(start + offset * DAY_MS).toISOString().slice(0, 10)
    const dayPoints = byDay.get(day) ?? []
    const withTokens = dayPoints.filter((point) => point.input_tokens != null || point.output_tokens != null)
    return {
      day,
      sessions: dayPoints.reduce((total, point) => total + point.session_count, 0),
      tokens:
        dayPoints.length === 0
          ? 0
          : withTokens.length === 0
            ? null
            : withTokens.reduce((total, point) => total + (point.input_tokens ?? 0) + (point.output_tokens ?? 0), 0),
      filters: dayFilters(dayPoints),
    }
  })
}

export function hasKnownTokens(points: ActivityPoint[]): boolean {
  return points.some((point) => point.input_tokens != null || point.output_tokens != null)
}

interface AggregateOptions {
  /** Name the source in each label: without a source filter, one name can appear once per source. */
  showSource?: boolean
}

function withSource(label: string, dataSourceId: number, showSource: boolean): string {
  return showSource ? `${label} · ${datasetLabel(dataSourceId)}` : label
}

export function aggregateTools(points: ToolPoint[], { showSource = false, limit = 6 }: AggregateOptions & { limit?: number } = {}) {
  return [...points]
    .sort((left, right) => right.call_count - left.call_count)
    .slice(0, limit)
    .map((point, index) => ({
      label: withSource(point.label, point.data_source_id, showSource),
      value: point.call_count,
      tone: CHART_TONES[index % CHART_TONES.length],
      filters: point.filters,
    }))
}

export function aggregateModels(points: ModelPoint[], { showSource = false }: AggregateOptions = {}) {
  return [...points]
    .sort((left, right) => right.call_count - left.call_count)
    .map((point, index) => ({
      label: withSource(point.label, point.data_source_id, showSource),
      value: point.call_count,
      tone: CHART_TONES[index % CHART_TONES.length],
      // `GET /sessions` has no "no model" filter: the point's filters, missing
      // `model_id`, would open every session of the source instead.
      filters: point.model_id == null ? null : point.filters,
    }))
}

export interface QualitySummary {
  recordsRead: number | null
  recordsImported: number | null
  recordsDuplicate: number | null
  recordsRejected: number | null
  issueCount: number | null
  fieldsMissing: number | null
  rejectionRatio: number | null
}

function sumFieldsMissing(fields: Record<string, number>): number {
  return Object.values(fields).reduce((total, count) => total + count, 0)
}

export function summarizeQuality(points: QualityPoint[]): QualitySummary {
  if (points.length === 0) {
    return {
      recordsRead: null,
      recordsImported: null,
      recordsDuplicate: null,
      recordsRejected: null,
      issueCount: null,
      fieldsMissing: null,
      rejectionRatio: null,
    }
  }

  const recordsRead = points.reduce((total, point) => total + point.records_read, 0)
  const recordsImported = points.reduce((total, point) => total + point.records_imported, 0)
  const recordsDuplicate = points.reduce((total, point) => total + point.records_duplicate, 0)
  const recordsRejected = points.reduce((total, point) => total + point.records_rejected, 0)
  const issueCount = points.reduce((total, point) => total + point.issue_count, 0)
  const fieldsMissing = points.reduce((total, point) => total + sumFieldsMissing(point.fields_missing), 0)

  return {
    recordsRead,
    recordsImported,
    recordsDuplicate,
    recordsRejected,
    issueCount,
    fieldsMissing,
    rejectionRatio: recordsRead === 0 ? null : recordsRejected / recordsRead,
  }
}

export function formatFieldsMissing(fields: Record<string, number> | null | undefined): string {
  if (!fields) return MISSING_VALUE
  const entries = Object.entries(fields).filter(([, count]) => count > 0)
  if (entries.length === 0) return MISSING_VALUE
  return entries.map(([field, count]) => `${field}: ${count}`).join(', ')
}
