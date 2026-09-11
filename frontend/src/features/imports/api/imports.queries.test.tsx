import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createTestQueryClient, withQueryClient } from '@/test/query'

const get = vi.fn()
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => get(...args),
    post: vi.fn(),
    postForm: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    del: vi.fn(),
  },
}))

const { useImportIssuesQuery, useImportQuery, IMPORT_POLL_INTERVAL_MS } = await import(
  '@/features/imports/api/imports.queries'
)

function run(status: string) {
  return {
    id: 5,
    status,
    report: { records_read: 1, records_inserted: 1, records_rejected: 0, records_duplicate: 0 },
  }
}

beforeEach(() => {
  get.mockReset()
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useImportQuery', () => {
  it('keeps polling while the run is not terminal', async () => {
    get.mockResolvedValue(run('running'))
    const client = createTestQueryClient()

    renderHook(() => useImportQuery(5), { wrapper: withQueryClient(client) })
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))

    await vi.advanceTimersByTimeAsync(IMPORT_POLL_INTERVAL_MS * 3)

    expect(get.mock.calls.length).toBeGreaterThan(1)
  })

  it('stops on its own once the run reaches a terminal status', async () => {
    get.mockResolvedValue(run('succeeded'))
    const client = createTestQueryClient()

    renderHook(() => useImportQuery(5), { wrapper: withQueryClient(client) })
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))

    await vi.advanceTimersByTimeAsync(IMPORT_POLL_INTERVAL_MS * 5)

    expect(get).toHaveBeenCalledTimes(1)
  })

  it('stops on error instead of hammering the API behind an error screen', async () => {
    // The bug this pins: `status` is undefined both before the first response
    // and after a failure, so returning the interval on `undefined` alone kept
    // `/imports/{unknown id}` requesting once a second for as long as the tab
    // stayed open.
    get.mockRejectedValue(new Error('404'))
    const client = createTestQueryClient()

    const { result } = renderHook(() => useImportQuery(99999), {
      wrapper: withQueryClient(client),
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
    const afterFailure = get.mock.calls.length

    await vi.advanceTimersByTimeAsync(IMPORT_POLL_INTERVAL_MS * 5)

    expect(get).toHaveBeenCalledTimes(afterFailure)
  })

  it('asks for nothing at all without a run id', () => {
    renderHook(() => useImportQuery(null), { wrapper: withQueryClient(createTestQueryClient()) })

    expect(get).not.toHaveBeenCalled()
  })
})

describe('when a run reaches a terminal status', () => {
  it('invalidates imports, files, sessions and the dashboard', async () => {
    // The bug this pins: the cache was invalidated at launch only, so the run
    // list kept showing `running` for a run that had finished.
    get.mockResolvedValueOnce(run('running')).mockResolvedValue(run('succeeded'))
    const client = createTestQueryClient()
    const invalidate = vi.spyOn(client, 'invalidateQueries')

    renderHook(() => useImportQuery(5), { wrapper: withQueryClient(client) })
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))
    expect(invalidate).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(IMPORT_POLL_INTERVAL_MS * 2)

    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(4))
    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey)
    expect(keys).toEqual(
      expect.arrayContaining([['imports'], ['files', 'detail'], ['sessions'], ['dashboard']]),
    )
  })

  it('invalidates nothing for a run that had already finished when first read', async () => {
    get.mockResolvedValue(run('failed'))
    const client = createTestQueryClient()
    const invalidate = vi.spyOn(client, 'invalidateQueries')

    renderHook(() => useImportQuery(5), { wrapper: withQueryClient(client) })
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))
    await vi.advanceTimersByTimeAsync(IMPORT_POLL_INTERVAL_MS * 3)

    expect(invalidate).not.toHaveBeenCalled()
  })
})

describe('useImportIssuesQuery', () => {
  it('polls while the run it belongs to is still moving', async () => {
    // The bug this pins: the issues query ran once, when the run had just been
    // accepted and had no issue yet. With `staleTime: 30s` and
    // `refetchOnWindowFocus: false` it never asked again, so a run that ended
    // `partial` rendered its cached empty page — "No issue recorded for this
    // run" on a run that rejected records.
    get.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 })
    const client = createTestQueryClient()

    renderHook(() => useImportIssuesQuery(5, undefined, { limit: 20 }, 'running'), {
      wrapper: withQueryClient(client),
    })
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))

    await vi.advanceTimersByTimeAsync(IMPORT_POLL_INTERVAL_MS * 3)

    expect(get.mock.calls.length).toBeGreaterThan(1)
  })

  it('stops once the run is terminal — a finished report never changes', async () => {
    get.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 })
    const client = createTestQueryClient()

    renderHook(() => useImportIssuesQuery(5, undefined, { limit: 20 }, 'partial'), {
      wrapper: withQueryClient(client),
    })
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))

    await vi.advanceTimersByTimeAsync(IMPORT_POLL_INTERVAL_MS * 5)

    expect(get).toHaveBeenCalledTimes(1)
  })

  it('polls while the run status is not known yet', async () => {
    get.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 })
    const client = createTestQueryClient()

    renderHook(() => useImportIssuesQuery(5, undefined, { limit: 20 }, undefined), {
      wrapper: withQueryClient(client),
    })
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))

    await vi.advanceTimersByTimeAsync(IMPORT_POLL_INTERVAL_MS * 3)

    expect(get.mock.calls.length).toBeGreaterThan(1)
  })

  it('passes the severity filter through, and omits it when asking for everything', async () => {
    get.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 })
    const client = createTestQueryClient()

    renderHook(() => useImportIssuesQuery(5, 'rejected', { limit: 20 }, 'succeeded'), {
      wrapper: withQueryClient(client),
    })

    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))
    expect(get.mock.calls[0][0]).toContain('severity=rejected')
  })
})
