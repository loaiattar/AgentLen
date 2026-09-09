import type { ActivityPoint, Metric, MetricDefinition, ModelPoint, ToolPoint } from '@/features/dashboard/types'

export const MISSING_VALUE = '—'

const numberFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 })
const compactFormat = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1,
})

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

export function sessionsByDay(points: ActivityPoint[]): number[] {
  const byDay = new Map<string, number>()
  for (const point of points) {
    byDay.set(point.day, (byDay.get(point.day) ?? 0) + point.session_count)
  }
  return [...byDay.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([, count]) => count)
}

export function knownTokensByDay(points: ActivityPoint[]): number[] {
  const byDay = new Map<string, number>()
  for (const point of points) {
    if (point.input_tokens == null && point.output_tokens == null) continue
    const known = (point.input_tokens ?? 0) + (point.output_tokens ?? 0)
    byDay.set(point.day, (byDay.get(point.day) ?? 0) + known)
  }
  return [...byDay.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([, tokens]) => tokens)
}

export function aggregateTools(points: ToolPoint[], limit = 6) {
  const byLabel = new Map<string, number>()
  for (const point of points) {
    byLabel.set(point.label, (byLabel.get(point.label) ?? 0) + point.call_count)
  }
  return [...byLabel.entries()]
    .sort(([, left], [, right]) => right - left)
    .slice(0, limit)
    .map(([label, value], index) => ({
      label,
      value,
      tone: CHART_TONES[index % CHART_TONES.length],
    }))
}

export function aggregateModels(points: ModelPoint[]) {
  const byLabel = new Map<string, number>()
  for (const point of points) {
    byLabel.set(point.label, (byLabel.get(point.label) ?? 0) + point.call_count)
  }
  return [...byLabel.entries()]
    .sort(([, left], [, right]) => right - left)
    .map(([label, value], index) => ({
      label,
      value,
      tone: CHART_TONES[index % CHART_TONES.length],
    }))
}
