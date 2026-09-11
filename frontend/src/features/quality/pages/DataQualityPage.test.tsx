import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { QualityPoint } from '@/features/dashboard/types'
import { DataQualityPage } from '@/features/quality/pages/DataQualityPage'
import { renderWithRouter } from '@/test/router'

function run(importRunId: number, imported: number): QualityPoint {
  return {
    import_run_id: importRunId,
    data_source_id: 1,
    status: imported > 0 ? 'succeeded' : 'failed',
    records_read: 4,
    records_imported: imported,
    records_duplicate: 0,
    records_rejected: 4 - imported,
    issue_count: 4 - imported,
    rejection_ratio: (4 - imported) / 4,
    fields_missing: {},
    filters: { import_run_id: importRunId, data_source_id: 1 },
  }
}

vi.mock('@/features/dashboard/hooks/useMetricsFilters', () => ({
  useMetricsFilters: () => ({ filters: {} }),
}))

vi.mock('@/features/dashboard/api/dashboard.queries', () => ({
  useDashboardQualityQuery: () => ({
    isPending: false,
    isError: false,
    error: null,
    data: { points: [run(7, 3), run(8, 0)], filters_applied: {}, warnings: [] },
    refetch: vi.fn(),
  }),
  useMetricDefinitionsQuery: () => ({ data: { definitions: [] } }),
}))

describe('DataQualityPage drill-down', () => {
  it('opens the sessions of an import from its row', async () => {
    const router = renderWithRouter(DataQualityPage)

    await userEvent.click(await screen.findByRole('link', { name: 'Sessions of import 7' }))

    expect(router.state.location.pathname).toBe('/sessions')
    expect(router.state.location.search).toEqual({ import_run_id: 7, data_source_id: 1 })
  })

  it('gives no link to an import that brought nothing in', async () => {
    renderWithRouter(DataQualityPage)

    expect(await screen.findByRole('link', { name: 'Sessions of import 7' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Sessions of import 8' })).not.toBeInTheDocument()
  })
})
