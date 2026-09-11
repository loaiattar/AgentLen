import { Link } from '@tanstack/react-router'
import type { FormEvent } from 'react'

import { Badge } from '@/components/ui/Badge'
import { BentoGrid, BentoModule } from '@/components/ui/Bento'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { FilterBar, FilterChip } from '@/components/ui/FilterBar'
import { Kpi } from '@/components/ui/Kpi'
import { OverflowMenu } from '@/components/ui/OverflowMenu'
import { PageHeader } from '@/components/ui/PageHeader'
import { SearchField } from '@/components/ui/SearchField'
import { GlassSkeleton } from '@/components/ui/Skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { IgnoredDatesNotice } from '@/features/dashboard/components/ActiveFilters'
import { filterChipLabel } from '@/features/dashboard/lib/filters'
import { useSessionsQuery } from '@/features/sessions/api/sessions.queries'
import { useSessionIdSearch, useSessionsSearch } from '@/features/sessions/hooks/useSessionsSearch'
import {
  formatCount,
  formatDurationMs,
  formatInstant,
  formatOutcome,
  outcomeTone,
  STATUS_FILTERS,
} from '@/features/sessions/lib/format'

export function SessionsListPage() {
  const {
    search,
    filters,
    limit,
    offset,
    hasActiveFilters,
    ignoredDates,
    setStatus,
    clearKey,
    clearFilters,
    dropIgnoredDates,
    setOffset,
    openSession,
    drillDownKeys,
  } = useSessionsSearch()
  const sessions = useSessionsQuery(filters, limit, offset)
  const idSearch = useSessionIdSearch()

  const onSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    idSearch.submit()
  }

  if (sessions.isPending) {
    return (
      <div>
        <PageHeader title="Sessions" />
        <BentoGrid>
          {Array.from({ length: 3 }, (_, index) => (
            <BentoModule key={index} cols={index === 0 ? 2 : 1} padding="none">
              <GlassSkeleton />
            </BentoModule>
          ))}
        </BentoGrid>
      </div>
    )
  }

  if (sessions.isError) {
    return (
      <div>
        <PageHeader title="Sessions" />
        <EmptyState
          title="Sessions unavailable"
          description={sessions.error?.message ?? 'Unable to load sessions.'}
          action={
            <Button variant="secondary" onClick={() => void sessions.refetch()}>
              Retry
            </Button>
          }
        />
      </div>
    )
  }

  const page = sessions.data
  const items = page?.items ?? []
  const total = page?.total ?? 0
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + items.length, total)
  // An empty page past the end is not an empty list: `total` still counts the matches.
  const pastLastPage = items.length === 0 && offset > 0
  const canPrev = offset > 0
  const canNext = offset + limit < total

  return (
    <div>
      <PageHeader title="Sessions" />
      <BentoGrid className="mb-8">
        <BentoModule cols={2} padding="none">
          <Kpi label="Matching sessions" value={formatCount(total)} />
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi
            label="This page"
            value={items.length === 0 ? '—' : `${formatCount(from)}–${formatCount(to)}`}
          />
        </BentoModule>
      </BentoGrid>

      <IgnoredDatesNotice messages={ignoredDates} onDismiss={dropIgnoredDates} />
      <FilterBar>
        <form onSubmit={onSearchSubmit} className="min-w-48 flex-1">
          <SearchField
            value={idSearch.value}
            onChange={(event) => idSearch.setValue(event.target.value)}
            placeholder="Open session id"
            aria-label="Open session by id"
          />
        </form>
        {STATUS_FILTERS.map((option) => (
          <FilterChip
            key={option.label}
            active={search.status === option.id}
            onClick={() => setStatus(option.id)}
          >
            {option.label}
          </FilterChip>
        ))}
        {drillDownKeys.map((key) => {
          const value = filters[key]
          if (value == null) return null
          return (
            <FilterChip
              key={key}
              active
              aria-label={`Remove filter ${filterChipLabel(key, value)}`}
              onClick={() => clearKey(key)}
            >
              {filterChipLabel(key, value)}
            </FilterChip>
          )
        })}
      </FilterBar>

      {pastLastPage ? (
        <EmptyState
          title="Past the last page"
          description={`${formatCount(total)} sessions match, all on earlier pages.`}
          action={
            <Button variant="secondary" onClick={() => setOffset(0)}>
              Back to first page
            </Button>
          }
        />
      ) : items.length === 0 ? (
        <EmptyState
          title={hasActiveFilters ? 'No matching sessions' : 'No sessions yet'}
          description={
            hasActiveFilters
              ? 'Nothing matches these filters. Clear them to widen the list.'
              : 'Sessions appear after an import. Until then, this list stays empty.'
          }
          action={
            hasActiveFilters ? (
              <Button variant="secondary" onClick={clearFilters}>
                Clear filters
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <div className="glass-surface rounded-xl p-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Session</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Agent</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((session) => (
                  <TableRow key={session.id}>
                    <TableCell>
                      <Link
                        to="/sessions/$sessionId"
                        params={{ sessionId: String(session.id) }}
                        search={(prev) => prev}
                        className="text-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary-emphasis/70"
                      >
                        {session.external_id || session.id}
                      </Link>
                    </TableCell>
                    <TableCell className="text-foreground-muted">{session.data_source_id}</TableCell>
                    <TableCell className="text-foreground-muted">
                      {session.agent_id == null ? '—' : session.agent_id}
                    </TableCell>
                    <TableCell>{formatDurationMs(session.duration_ms)}</TableCell>
                    <TableCell className="text-foreground-muted">{formatInstant(session.started_at)}</TableCell>
                    <TableCell>
                      <Badge tone={outcomeTone(session.outcome)}>{formatOutcome(session.outcome)}</Badge>
                    </TableCell>
                    <TableCell>
                      <OverflowMenu
                        items={[{ label: 'Open', onSelect: () => openSession(session.id) }]}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="mt-4 flex items-center justify-between gap-3">
            <p className="text-secondary text-foreground-muted">
              {formatCount(from)}–{formatCount(to)} of {formatCount(total)}
            </p>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={!canPrev} onClick={() => setOffset(Math.max(0, offset - limit))}>
                Previous
              </Button>
              <Button variant="secondary" size="sm" disabled={!canNext} onClick={() => setOffset(offset + limit)}>
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
