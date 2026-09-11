import { describe, expect, it, vi } from 'vitest'

import { loadAllPages, truncationNotice, withWindow, type PageResult } from '@/lib/api/pagination'

/** A route holding `count` rows that reports `total` (defaults to `count`). */
function route(count: number, total: number | null = count) {
  const rows = Array.from({ length: count }, (_, index) => index)
  return vi.fn(async (limit: number, offset: number): Promise<PageResult<number>> => ({
    items: rows.slice(offset, offset + limit),
    total,
  }))
}

describe('loadAllPages', () => {
  it('reads 250 rows across two pages of 200', async () => {
    const fetchPage = route(250)

    const list = await loadAllPages(fetchPage)

    expect(fetchPage.mock.calls).toEqual([
      [200, 0],
      [200, 200],
    ])
    expect(list).toEqual({ items: Array.from({ length: 250 }, (_, i) => i), total: 250, truncated: false })
  })

  it('stops at the ceiling and says the list is cut short', async () => {
    const fetchPage = route(1000)

    const list = await loadAllPages(fetchPage, 300)

    expect(fetchPage.mock.calls).toEqual([
      [200, 0],
      [100, 200],
    ])
    expect(list.items).toHaveLength(300)
    expect(list).toMatchObject({ total: 1000, truncated: true })
  })

  it('stops on a short page even when the total promised more', async () => {
    const fetchPage = route(200, 300)

    const list = await loadAllPages(fetchPage)

    expect(fetchPage).toHaveBeenCalledTimes(2)
    expect(list).toMatchObject({ total: 300, truncated: true })
  })

  it('does not page past a full page without a total, and flags it', async () => {
    const fetchPage = route(500, null)

    const list = await loadAllPages(fetchPage)

    expect(fetchPage).toHaveBeenCalledTimes(1)
    expect(list).toMatchObject({ total: null, truncated: true })
  })
})

describe('truncationNotice', () => {
  it('says how many of the total are shown', () => {
    expect(truncationNotice({ items: new Array(2000), total: 2345, truncated: true }, 'events')).toBe(
      'Showing 2,000 of 2,345 events.',
    )
  })

  it('says nothing about a complete list', () => {
    expect(truncationNotice({ items: [1], total: 1, truncated: false }, 'events')).toBeNull()
  })

  it('does not invent a total the API did not report', () => {
    expect(truncationNotice({ items: new Array(200), total: null, truncated: true }, 'events')).toBe(
      'Showing the first 200 events: the API reported no total.',
    )
  })
})

describe('withWindow', () => {
  it('appends to a path with or without a query', () => {
    expect(withWindow('/mappings', 200, 0)).toBe('/mappings?limit=200&offset=0')
    expect(withWindow('/mappings?data_source_id=3', 200, 400)).toBe('/mappings?data_source_id=3&limit=200&offset=400')
  })
})
