import type { SessionStatus } from '@/features/dashboard/lib/filters'
import type { BadgeProps } from '@/components/ui/Badge'

export const MISSING_VALUE = '—'

const durationFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

const instantFormat = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

export function formatDurationMs(value: number | null | undefined): string {
  if (value == null) return MISSING_VALUE
  const totalSeconds = Math.round(value / 1000)
  if (totalSeconds < 60) return `${totalSeconds}s`
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return seconds === 0 ? `${minutes}m` : `${minutes}m ${seconds}s`
}

export function formatCount(value: number | null | undefined): string {
  if (value == null) return MISSING_VALUE
  return durationFormat.format(value)
}

export function formatInstant(value: string | null | undefined): string {
  if (!value) return MISSING_VALUE
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return MISSING_VALUE
  return instantFormat.format(date)
}

export function outcomeTone(outcome: string | null | undefined): BadgeProps['tone'] {
  if (outcome === 'completed') return 'mint'
  if (outcome === 'error') return 'pink'
  if (outcome === 'aborted') return 'warning'
  if (outcome === 'unknown') return 'neutral'
  return 'neutral'
}

export function formatOutcome(outcome: string | null | undefined): string {
  if (!outcome) return MISSING_VALUE
  return outcome
}

export const STATUS_FILTERS: Array<{ id: SessionStatus | undefined; label: string }> = [
  { id: undefined, label: 'All statuses' },
  { id: 'completed', label: 'Completed' },
  { id: 'error', label: 'Error' },
  { id: 'aborted', label: 'Aborted' },
  { id: 'unknown', label: 'Unknown' },
]
