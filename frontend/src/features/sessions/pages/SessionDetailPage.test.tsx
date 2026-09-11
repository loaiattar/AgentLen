import { render, screen, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SessionDetailPage } from '@/features/sessions/pages/SessionDetailPage'
import { createTestQueryClient, withQueryClient } from '@/test/query'

vi.mock('@tanstack/react-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@tanstack/react-router')>()),
  getRouteApi: () => ({ useParams: () => ({ sessionId: '7' }) }),
  Link: ({ children }: { children: ReactNode }) => <a href="/sessions">{children}</a>,
}))

function toolCall(index: number) {
  return {
    type: 'tool_call',
    event: { id: index, session_id: 7, raw_record_id: 1, tool_id: 1, sequence_index: index, status: 'ok' },
  }
}

const SESSION = {
  session: { id: 7, data_source_id: 1, raw_record_id: 1, external_id: 'run-7', agent_id: null, outcome: null },
  model_calls: [],
  tool_calls: [],
}

/** Serves the session, and a timeline of `count` events claiming `total` in X-Total-Count. */
function serve(count: number, total: number) {
  const events = Array.from({ length: count }, (_, index) => toolCall(index))
  const fetchMock = vi.fn(async (url: string) => {
    const { pathname, searchParams } = new URL(url, 'http://test')
    if (!pathname.endsWith('/timeline')) return new Response(JSON.stringify(SESSION))
    const limit = Number(searchParams.get('limit'))
    const offset = Number(searchParams.get('offset'))
    return new Response(JSON.stringify(events.slice(offset, offset + limit)), {
      headers: { 'X-Total-Count': String(total) },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPage() {
  const Wrapper = withQueryClient(createTestQueryClient())
  return render(<SessionDetailPage />, { wrapper: Wrapper })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SessionDetailPage timeline', () => {
  it('shows all 250 events of a session the API sends in two pages', async () => {
    const fetchMock = serve(250, 250)

    renderPage()

    const timeline = await screen.findByRole('list')
    expect(within(timeline).getAllByRole('listitem')).toHaveLength(250)
    expect(screen.getByText('Tool call · #249')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    const timelineUrls = fetchMock.mock.calls.map(([url]) => url).filter((url) => url.includes('/timeline'))
    expect(timelineUrls).toEqual([
      '/api/v1/sessions/7/timeline?limit=200&offset=0',
      '/api/v1/sessions/7/timeline?limit=200&offset=200',
    ])
  })

  it('says the timeline is partial when the API holds more than it served', async () => {
    serve(200, 300)

    renderPage()

    expect(await screen.findByRole('status')).toHaveTextContent('Showing 200 of 300 events.')
    expect(within(screen.getByRole('list')).getAllByRole('listitem')).toHaveLength(200)
  })
})
