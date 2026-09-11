import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { SessionsPage } from '@/features/sessions/types'
import { SessionsListPage } from '@/features/sessions/pages/SessionsListPage'
import { renderInAppLayout } from '@/test/app-router'

const state = vi.hoisted(() => ({ page: { items: [], total: 0, limit: 50, offset: 0 } as SessionsPage }))

vi.mock('@/features/sessions/api/sessions.queries', () => ({
  useSessionsQuery: () => ({ isPending: false, isError: false, error: null, data: state.page, refetch: vi.fn() }),
}))

beforeEach(() => {
  state.page = { items: [], total: 0, limit: 50, offset: 0 }
})

describe('SessionsListPage filters', () => {
  it('says the list is empty only when nothing narrows it', async () => {
    renderInAppLayout(SessionsListPage, { path: 'sessions', url: '/sessions' })

    expect(await screen.findByText('No sessions yet')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument()
  })

  it('counts the header dataset and period as filters, and clears them too', async () => {
    const router = renderInAppLayout(SessionsListPage, { path: 'sessions', url: '/sessions?data_source_id=4&period=7d' })

    expect(await screen.findByText('No matching sessions')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))

    await waitFor(() => expect(router.state.location.search).toEqual({}))
  })

  it('offers the first page back when the offset is past the last match', async () => {
    state.page = { items: [], total: 12, limit: 50, offset: 100 }
    const router = renderInAppLayout(SessionsListPage, { path: 'sessions', url: '/sessions?status=error&offset=100' })

    expect(await screen.findByText('Past the last page')).toBeInTheDocument()
    expect(screen.queryByText('No sessions yet')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Back to first page' }))

    await waitFor(() => expect(router.state.location.search).toEqual({ status: 'error' }))
  })

  it('labels a date drill-down in UTC and removes it', async () => {
    const router = renderInAppLayout(SessionsListPage, {
      path: 'sessions',
      url: '/sessions?date_from=2026-09-01T00:00:00%2B00:00&tool_id=3',
    })

    await userEvent.click(await screen.findByRole('button', { name: /^Remove filter From 01 Sept?,? 00:00 UTC$/ }))

    await waitFor(() => expect(router.state.location.search).toEqual({ tool_id: 3 }))
  })

  it('tells that an inverted date range was ignored', async () => {
    renderInAppLayout(SessionsListPage, { path: 'sessions', url: '/sessions?date_from=2026-09-03&date_to=2026-09-01' })

    expect(await screen.findByRole('status')).toHaveTextContent('ends before it starts')
    expect(screen.queryByRole('button', { name: /Remove filter From/ })).not.toBeInTheDocument()
  })
})
