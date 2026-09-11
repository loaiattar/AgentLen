import { describe, expect, it } from 'vitest'

import {
  datasetLabel,
  datasetOptions,
  parseInstant,
  parseMetricsSearch,
  periodLabel,
  readDateRange,
  resolvePeriod,
  searchToDashboardFilters,
  withoutIgnoredDates,
  withoutSearchKeys,
} from '@/features/dashboard/lib/filters'

describe('parseInstant', () => {
  it('reads the forms the API sends and accepts', () => {
    expect(parseInstant('2026-09-01T00:00:00+00:00')).toBe(Date.UTC(2026, 8, 1))
    expect(parseInstant('2026-09-04T10:00:00.000Z')).toBe(Date.UTC(2026, 8, 4, 10))
    expect(parseInstant('2026-09-01T02:00:00+02:00')).toBe(Date.UTC(2026, 8, 1))
    expect(parseInstant('2026-09-01')).toBe(Date.UTC(2026, 8, 1))
    // Without an offset the API's calendar applies, not the browser's.
    expect(parseInstant('2026-09-01T10:30')).toBe(Date.UTC(2026, 8, 1, 10, 30))
  })

  it('refuses what the API answers 400 to, even when Date.parse reads it', () => {
    for (const value of ['last-week', 'September 1, 2026', '2026/09/01', '2026-02-30', '2026-09-01T24:00:00Z', '', 20260901]) {
      expect(parseInstant(value), String(value)).toBeUndefined()
    }
  })
})

describe('readDateRange', () => {
  it('ignores an unreadable date and says which one', () => {
    const { dates, ignored } = readDateRange({ date_from: 'last-week', date_to: '2026-09-02T00:00:00Z' })

    expect(dates).toEqual({ date_to: '2026-09-02T00:00:00Z' })
    expect(ignored).toEqual(['The start date “last-week” is not a date: it is ignored.'])
  })

  it('ignores both dates of a range that ends before it starts', () => {
    const { dates, ignored } = readDateRange({ date_from: '2026-09-03', date_to: '2026-09-01T00:00:00Z' })

    expect(dates).toEqual({})
    expect(ignored).toEqual(['The date range ends before it starts: both dates are ignored.'])
  })

  it('has nothing to say about a valid range or no dates at all', () => {
    expect(readDateRange({ date_from: '2026-09-01', date_to: '2026-09-01' })).toEqual({
      dates: { date_from: '2026-09-01', date_to: '2026-09-01' },
      ignored: [],
    })
    expect(readDateRange({})).toEqual({ dates: {}, ignored: [] })
  })
})

describe('parseMetricsSearch', () => {
  it('keeps invalid dates out of the filters, so no metric request gets a 400', () => {
    const search = parseMetricsSearch({ date_from: 'last-week', status: 'error', data_source_id: 2 })

    expect(search).toEqual({ status: 'error', data_source_id: 2 })
    expect(resolvePeriod(searchToDashboardFilters(search))).not.toHaveProperty('date_from')
  })

  it('resets every rejected key but the dates, since the router spreads the raw URL underneath', () => {
    const search = parseMetricsSearch({ date_from: 'last-week', status: 'bogus', data_source_id: 'abc', offset: 0 })

    expect({ ...search }).toStrictEqual({
      status: undefined,
      data_source_id: undefined,
      offset: undefined,
    })
  })
})

describe('searchToDashboardFilters', () => {
  it('reads dates only once validated, since the raw ones stay in the search', () => {
    expect(searchToDashboardFilters({ date_from: 'last-week', period: '7d' })).toEqual({ period: '7d' })
    expect(searchToDashboardFilters({ date_from: '2026-09-03', date_to: '2026-09-01', period: '7d' })).toEqual({ period: '7d' })
    expect(periodLabel({ date_from: 'last-week', period: '7d' })).toBe('Last 7 days')
  })
})

describe('withoutIgnoredDates', () => {
  it('takes only the ignored dates out of the link', () => {
    expect(withoutIgnoredDates({ date_from: 'last-week', date_to: '2026-09-02', offset: 50 })).toEqual({
      date_to: '2026-09-02',
      offset: 50,
    })
    expect(withoutIgnoredDates({ date_from: '2026-09-03', date_to: '2026-09-01', status: 'error' })).toEqual({ status: 'error' })
  })
})

describe('withoutSearchKeys', () => {
  it('drops the filter and the page, and keeps the rest', () => {
    expect(withoutSearchKeys({ status: 'error', data_source_id: 1, period: '7d', offset: 50 }, ['status'])).toEqual({
      data_source_id: 1,
      period: '7d',
    })
  })

  it('drops the hidden period only with a date that was there', () => {
    expect(withoutSearchKeys({ date_from: '2026-09-01', period: '7d' }, ['date_from'])).toEqual({})
    expect(withoutSearchKeys({ tool_id: 3, period: '7d' }, ['tool_id', 'date_from'])).toEqual({ period: '7d' })
  })
})

describe('dataset options', () => {
  const sources = [
    { id: 1, name: 'TraceLab' },
    { id: 4, name: 'Imported from the UI' },
  ]

  it('lists every source the API declares', () => {
    expect(datasetOptions({ data: sources, isPending: false, isError: false })).toEqual([
      { id: undefined, label: 'All datasets' },
      { id: 1, label: 'TraceLab' },
      { id: 4, label: 'Imported from the UI' },
    ])
  })

  it('says why the list is short instead of inventing sources', () => {
    expect(datasetOptions({ isPending: true, isError: false }).at(-1)).toEqual({
      id: undefined,
      label: 'Loading sources…',
      disabled: true,
    })
    expect(datasetOptions({ isPending: false, isError: true }).map((option) => option.label)).toEqual([
      'All datasets',
      'Sources unavailable',
    ])
  })

  it('names the selected source, or its id when the API does not list it', () => {
    expect(datasetLabel(4, sources)).toBe('Imported from the UI')
    expect(datasetLabel(9, sources)).toBe('Source 9')
    expect(datasetLabel(undefined, sources)).toBe('All datasets')
  })
})

describe('periodLabel', () => {
  it('does not name a period that dates override', () => {
    expect(periodLabel({ period: '7d' })).toBe('Last 7 days')
    expect(periodLabel({ period: '7d', date_from: '2026-09-01' })).toBe('Custom range')
    expect(periodLabel({})).toBe('All time')
  })
})
