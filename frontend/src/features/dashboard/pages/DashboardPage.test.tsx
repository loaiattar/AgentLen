import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { formatDay } from '@/features/dashboard/lib/format'
import { DashboardPage } from '@/features/dashboard/pages/DashboardPage'
import type { ActivityPoint, DashboardFilters, ModelPoint } from '@/features/dashboard/types'
import { renderWithRouter } from '@/test/router'

const state = vi.hoisted(() => ({ filters: {} as DashboardFilters, activityWarnings: [] as string[] }))

function loaded<T>(data: T) {
  return { isPending: false, isError: false, error: null, data, refetch: vi.fn() }
}

function activity(day: string, dataSourceId: number, sessions: number, tokens: number | null): ActivityPoint {
  return {
    day,
    data_source_id: dataSourceId,
    session_count: sessions,
    model_call_count: 0,
    tool_call_count: 0,
    input_tokens: tokens,
    output_tokens: null,
    coverage: { present: tokens == null ? 0 : 1, total: 1, ratio: tokens == null ? 0 : 1 },
    filters: { data_source_id: dataSourceId, date_from: `${day}T00:00:00+00:00`, date_to: `${day}T23:59:59+00:00` },
  }
}

function model(label: string, modelId: number | null, calls: number): ModelPoint {
  return {
    label,
    model_id: modelId,
    provider_name: null,
    data_source_id: 1,
    call_count: calls,
    input_tokens: null,
    output_tokens: null,
    coverage: { present: 0, total: calls, ratio: 0 },
    cache_read_tokens: null,
    cache_coverage: { present: 0, total: calls, ratio: 0 },
    filters: modelId == null ? { data_source_id: 1 } : { model_id: modelId, data_source_id: 1 },
  }
}

vi.mock('@/features/dashboard/hooks/useMetricsFilters', () => ({
  useMetricsFilters: () => ({ filters: state.filters }),
}))

vi.mock('@/features/dashboard/api/dashboard.queries', () => {
  const points = <T,>(items: T[]) => loaded({ points: items, filters_applied: {}, warnings: [] })
  return {
    useDashboardOverviewQuery: () => loaded({ metrics: [], filters_applied: {} }),
    useDashboardActivityQuery: () =>
      loaded({
        points: [
          activity('2026-09-01', 1, 2, 120),
          activity('2026-09-02', 1, 1, null),
          activity('2026-09-04', 1, 1, 10),
          activity('2026-09-04', 2, 3, 10),
        ],
        filters_applied: {},
        warnings: state.activityWarnings,
      }),
    useDashboardToolsQuery: () => points([]),
    useDashboardModelsQuery: () => points([model('model-a', 5, 8), model('unknown', null, 2)]),
    useDashboardQualityQuery: () => points([]),
    useMetricDefinitionsQuery: () => loaded({ definitions: [] }),
  }
})

// Day names below come from `formatDay`: the runtime's ICU data says "Sep" or "Sept".
describe('DashboardPage drill-down', () => {
  beforeEach(() => {
    state.filters = {}
    state.activityWarnings = []
  })

  it('says why sessions are missing from the activity chart', async () => {
    const warning = "1 session(s) sur 8 sans date de début, absente(s) de cette série : ni la source ni les appels de ces sessions ne portent d'horodatage mappé."
    state.activityWarnings = [warning]
    renderWithRouter(DashboardPage)

    expect(await screen.findByText(warning)).toBeInTheDocument()
  })

  it('opens the sessions of a day from the activity chart', async () => {
    const router = renderWithRouter(DashboardPage)

    await userEvent.click(await screen.findByRole('link', { name: `${formatDay('2026-09-01')}: 2 sessions` }))

    expect(router.state.location.pathname).toBe('/sessions')
    expect(router.state.location.search).toEqual({
      data_source_id: 1,
      date_from: '2026-09-01T00:00:00+00:00',
      date_to: '2026-09-01T23:59:59+00:00',
    })
  })

  it('opens every source of a day shared by several', async () => {
    const router = renderWithRouter(DashboardPage)

    await userEvent.click(await screen.findByRole('link', { name: `${formatDay('2026-09-04')}: 4 sessions` }))

    expect(router.state.location.search).not.toHaveProperty('data_source_id')
  })

  it('draws the empty day but gives it no link', async () => {
    renderWithRouter(DashboardPage)

    expect(await screen.findByRole('link', { name: `${formatDay('2026-09-02')}: 1 sessions` })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: new RegExp(`^${formatDay('2026-09-03')}`) })).not.toBeInTheDocument()
  })

  it('links a day with unknown tokens from the token chart, saying so', async () => {
    renderWithRouter(DashboardPage)

    expect(await screen.findByRole('link', { name: `${formatDay('2026-09-02')}: tokens not reported` })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: `${formatDay('2026-09-01')}: 120 known tokens` })).toBeInTheDocument()
  })

  it('does not turn the unknown model into a link to the whole source', async () => {
    renderWithRouter(DashboardPage)

    const modelLink = await screen.findByRole('link', { name: /model-a · TraceLab/ })
    expect(within(modelLink).getByText('80%')).toBeInTheDocument()
    expect(screen.getByText('unknown · TraceLab')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /unknown/ })).not.toBeInTheDocument()
    expect(screen.getByText(/no model name/)).toBeInTheDocument()
  })

  it('drops the source from labels once a source is selected', async () => {
    state.filters = { data_source_id: 1 }
    renderWithRouter(DashboardPage)

    expect(await screen.findByRole('link', { name: /^model-a/ })).toBeInTheDocument()
    expect(screen.queryByText(/· TraceLab/)).not.toBeInTheDocument()
  })
})
