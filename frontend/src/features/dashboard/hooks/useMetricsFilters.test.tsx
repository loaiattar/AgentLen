import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ActiveFilters } from '@/features/dashboard/components/ActiveFilters'
import { useMetricsFilters } from '@/features/dashboard/hooks/useMetricsFilters'
import { renderInAppLayout } from '@/test/app-router'

const sources = vi.hoisted(() => ({
  current: { data: undefined as { id: number; name: string }[] | undefined, isPending: false, isError: false },
}))

vi.mock('@/features/imports/api/imports.queries', () => ({
  useDataSourcesQuery: () => sources.current,
}))

/** What the header and the dashboard read, rendered where a test can see it. */
function Probe() {
  const metrics = useMetricsFilters()
  return (
    <div>
      <p>dataset: {metrics.datasetLabel}</p>
      <p>period: {metrics.periodLabel}</p>
      <p>options: {metrics.datasetOptions.map((option) => option.label).join(', ')}</p>
      <p>filters: {JSON.stringify(metrics.filters)}</p>
      <ActiveFilters
        filters={metrics.filters}
        ignoredDates={metrics.ignoredDates}
        onRemove={metrics.removeFilter}
        onClear={metrics.clearExploration}
        onDropIgnoredDates={metrics.dropIgnoredDates}
      />
    </div>
  )
}

beforeEach(() => {
  sources.current = { data: [{ id: 1, name: 'TraceLab' }, { id: 7, name: 'Upload from the UI' }], isPending: false, isError: false }
})

describe('useMetricsFilters', () => {
  it('offers and names the sources the API returns', async () => {
    renderInAppLayout(Probe, { path: 'overview', url: '/overview?data_source_id=7' })

    expect(await screen.findByText('dataset: Upload from the UI')).toBeInTheDocument()
    expect(screen.getByText('options: All datasets, TraceLab, Upload from the UI')).toBeInTheDocument()
  })

  it('shows filters carried over from the sessions page, and removes one', async () => {
    const router = renderInAppLayout(Probe, { path: 'overview', url: '/overview?status=error&tool_id=3&data_source_id=1&offset=50' })

    await userEvent.click(await screen.findByRole('button', { name: 'Remove filter Status error' }))

    await waitFor(() => expect(router.state.location.search).toEqual({ tool_id: 3, data_source_id: 1 }))
    expect(screen.queryByRole('button', { name: /Status error/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove filter Tool 3' })).toBeInTheDocument()
  })

  it('clears the carried-over filters but keeps the header dataset and period', async () => {
    const router = renderInAppLayout(Probe, { path: 'overview', url: '/overview?status=error&model_id=2&period=7d&data_source_id=1' })

    await userEvent.click(await screen.findByRole('button', { name: 'Clear filters' }))

    await waitFor(() => expect(router.state.location.search).toEqual({ period: '7d', data_source_id: 1 }))
    expect(screen.queryByRole('group', { name: 'Active filters' })).not.toBeInTheDocument()
  })

  it('ignores an invalid date, says so, and takes it out of the link', async () => {
    const router = renderInAppLayout(Probe, { path: 'overview', url: '/overview?date_from=last-week&status=error' })

    expect(await screen.findByRole('status')).toHaveTextContent('The start date “last-week” is not a date')
    // The link keeps what it asked for; no request and no chip get the date.
    expect(router.state.location.search).toEqual({ date_from: 'last-week', status: 'error' })
    expect(screen.getByText('filters: {"status":"error"}')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Remove filter From/ })).not.toBeInTheDocument()
    expect(screen.getByText('period: All time')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Remove from link' }))

    await waitFor(() => expect(router.state.location.search).toEqual({ status: 'error' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('names a date range instead of the period it overrides', async () => {
    renderInAppLayout(Probe, { path: 'overview', url: '/overview?period=7d&date_from=2026-09-01T00:00:00Z' })

    expect(await screen.findByText('period: Custom range')).toBeInTheDocument()
  })
})
