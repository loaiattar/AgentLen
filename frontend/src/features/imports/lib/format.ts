import type { ImportRunStatus, ImportSeverity } from '@/features/imports/types'

type BadgeTone = 'neutral' | 'cyan' | 'mint' | 'magenta' | 'pink' | 'blue' | 'warning'
type DotTone = 'live' | 'success' | 'warning' | 'error' | 'muted' | 'ai'

const statusTones: Record<ImportRunStatus, { badge: BadgeTone; dot: DotTone }> = {
  pending: { badge: 'neutral', dot: 'muted' },
  running: { badge: 'cyan', dot: 'live' },
  succeeded: { badge: 'mint', dot: 'success' },
  partial: { badge: 'warning', dot: 'warning' },
  failed: { badge: 'pink', dot: 'error' },
  cancelled: { badge: 'neutral', dot: 'muted' },
}

export function statusTone(status: ImportRunStatus) {
  return statusTones[status] ?? statusTones.pending
}

const severityTones: Record<ImportSeverity, BadgeTone> = {
  rejected: 'pink',
  duplicate: 'blue',
  warning: 'warning',
}

export function severityTone(severity: ImportSeverity): BadgeTone {
  return severityTones[severity] ?? 'neutral'
}

const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB']

export function formatBytes(bytes: number): string {
  if (bytes < 1) return '0 B'
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), BYTE_UNITS.length - 1)
  const value = bytes / 1024 ** exponent
  return `${value.toFixed(exponent === 0 ? 0 : 1)} ${BYTE_UNITS[exponent]}`
}

export function formatCount(value: number | null | undefined): string {
  // A count the API did not provide is not zero (ARCHITECTURE §2).
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('en-US')
}

export function formatRatio(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined) return '—'
  // Both ends need decimals, not just the low one. At 0 places a `null_ratio`
  // of 0.996 read "100%" — "this column is entirely empty" for a column that
  // has values — and a `distinct_ratio` of 0.996 read as a unique key. Exact 0
  // and exact 1 stay "0%" and "100%", which is the whole point of the reading.
  const percent = ratio * 100
  if (ratio <= 0 || ratio >= 1) return `${percent.toFixed(0)}%`
  if (percent < 1 || percent > 99) return `${percent.toFixed(2)}%`
  return `${percent.toFixed(0)}%`
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDuration(startedAt: string | null, finishedAt: string | null): string {
  if (!startedAt || !finishedAt) return '—'
  const ms = new Date(finishedAt).getTime() - new Date(startedAt).getTime()
  if (Number.isNaN(ms) || ms < 0) return '—'
  if (ms < 1000) return `${ms} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  const minutes = Math.floor(ms / 60_000)
  const seconds = Math.round((ms % 60_000) / 1000)
  return `${minutes} min ${seconds.toString().padStart(2, '0')} s`
}

/** Truncates an example value so one pathological row cannot blow up a cell. */
export function truncate(value: string, max = 64): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value
}

export function formatExample(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return truncate(value)
  return truncate(JSON.stringify(value))
}

/** `{ session: 20, model_call: 143 }` -> `"session 20 · model_call 143"`. */
export function summarizeCounts(counts: Record<string, number>): string {
  const entries = Object.entries(counts)
  if (entries.length === 0) return '—'
  return entries.map(([target, count]) => `${target} ${formatCount(count)}`).join(' · ')
}

export function totalCount(counts: Record<string, number>): number {
  return Object.values(counts).reduce((sum, value) => sum + value, 0)
}
