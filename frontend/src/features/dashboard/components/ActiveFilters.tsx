import { X } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { FilterBar, FilterChip } from '@/components/ui/FilterBar'
import {
  EXPLORATION_KEYS,
  filterChipLabel,
  type ExplorationKey,
} from '@/features/dashboard/lib/filters'
import type { DashboardFilters } from '@/features/dashboard/types'

export function IgnoredDatesNotice({ messages, onDismiss }: { messages: string[]; onDismiss: () => void }) {
  if (messages.length === 0) return null
  return (
    <div
      role="status"
      className="mb-[var(--space-3)] flex flex-wrap items-center justify-between gap-[var(--space-1)] rounded-xl bg-warning-soft px-[var(--space-2)] py-[var(--space-2)] text-body text-foreground"
    >
      <ul className="grid gap-1">
        {messages.map((message) => (
          <li key={message}>{message}</li>
        ))}
      </ul>
      <Button variant="secondary" size="sm" onClick={onDismiss}>
        Remove from link
      </Button>
    </div>
  )
}

export interface ActiveFiltersProps {
  /** Validated filters: an ignored date gets a notice, not a chip. */
  filters: DashboardFilters
  ignoredDates: string[]
  onRemove: (key: ExplorationKey) => void
  onClear: () => void
  onDropIgnoredDates: () => void
}

/**
 * The filters a page applies beyond the header's dataset and period — carried
 * over from a drill-down on another page — each one visible and removable.
 */
export function ActiveFilters({ filters, ignoredDates, onRemove, onClear, onDropIgnoredDates }: ActiveFiltersProps) {
  const chips = EXPLORATION_KEYS.flatMap((key) => {
    const value = filters[key]
    return value == null ? [] : [{ key, label: filterChipLabel(key, value) }]
  })

  return (
    <>
      <IgnoredDatesNotice messages={ignoredDates} onDismiss={onDropIgnoredDates} />
      {chips.length > 0 ? (
        <FilterBar role="group" aria-label="Active filters">
          <span className="text-secondary text-foreground-subtle">Filtered by</span>
          {chips.map((chip) => (
            <FilterChip
              key={chip.key}
              active
              aria-label={`Remove filter ${chip.label}`}
              className="inline-flex items-center gap-1"
              onClick={() => onRemove(chip.key)}
            >
              {chip.label}
              <X aria-hidden className="size-3" />
            </FilterChip>
          ))}
          <Button variant="ghost" size="sm" onClick={onClear}>
            Clear filters
          </Button>
        </FilterBar>
      ) : null}
    </>
  )
}
