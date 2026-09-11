import { describe, expect, it } from 'vitest'

import { aggregateModels, aggregateTools, dailySeries, hasKnownTokens } from '@/features/dashboard/lib/format'
import type { ActivityPoint, ModelPoint, ToolPoint } from '@/features/dashboard/types'

function activity(day: string, overrides: Partial<ActivityPoint> = {}): ActivityPoint {
  const dataSourceId = overrides.data_source_id ?? 1
  return {
    day,
    data_source_id: dataSourceId,
    session_count: 1,
    model_call_count: 0,
    tool_call_count: 0,
    input_tokens: 10,
    output_tokens: 5,
    coverage: { present: 1, total: 1, ratio: 1 },
    filters: {
      data_source_id: dataSourceId,
      date_from: `${day}T00:00:00+00:00`,
      date_to: `${day}T23:59:59+00:00`,
    },
    ...overrides,
  }
}

describe('dailySeries', () => {
  it('draws sparse activity on a continuous day axis, with a true 0 between', () => {
    // The bug this pins: Sep 1, 2 and 10 were drawn as three consecutive days.
    const days = dailySeries([
      activity('2026-09-01', { session_count: 2 }),
      activity('2026-09-02'),
      activity('2026-09-10', { session_count: 4 }),
    ])

    expect(days.map((bucket) => bucket.day)).toEqual([
      '2026-09-01',
      '2026-09-02',
      '2026-09-03',
      '2026-09-04',
      '2026-09-05',
      '2026-09-06',
      '2026-09-07',
      '2026-09-08',
      '2026-09-09',
      '2026-09-10',
    ])
    expect(days.map((bucket) => bucket.sessions)).toEqual([2, 1, 0, 0, 0, 0, 0, 0, 0, 4])
  })

  it('keeps sessions and tokens the same length, with a gap only where tokens are unknown', () => {
    const days = dailySeries([
      activity('2026-09-01', { input_tokens: 100, output_tokens: null }),
      activity('2026-09-02', { input_tokens: null, output_tokens: null }),
      activity('2026-09-04'),
    ])

    expect(days.map((bucket) => bucket.tokens)).toEqual([100, null, 0, 15])
    expect(days.map((bucket) => bucket.sessions)).toHaveLength(4)
  })

  it('does not link a day without sessions: there is nothing to open', () => {
    const days = dailySeries([activity('2026-09-01'), activity('2026-09-03')])

    expect(days[0]?.filters).toEqual(activity('2026-09-01').filters)
    expect(days[1]?.filters).toBeNull()
  })

  it('opens every source of a day that has several, and keeps the source otherwise', () => {
    const [shared] = dailySeries([
      activity('2026-09-01', { data_source_id: 1 }),
      activity('2026-09-01', { data_source_id: 2 }),
    ])

    expect(shared?.sessions).toBe(2)
    expect(shared?.filters).not.toHaveProperty('data_source_id')
    expect(shared?.filters).toHaveProperty('date_from', '2026-09-01T00:00:00+00:00')
  })

  it('spans the requested range, and a range ending at midnight does not add the next day', () => {
    const days = dailySeries([activity('2026-09-01')], {
      date_from: '2026-08-30T10:00:00.000Z',
      date_to: '2026-09-03T00:00:00+00:00',
    })

    expect(days.map((bucket) => bucket.day)).toEqual(['2026-08-30', '2026-08-31', '2026-09-01', '2026-09-02'])
  })

  it('widens a range narrower than the data rather than hiding points', () => {
    const days = dailySeries([activity('2026-09-01'), activity('2026-09-03')], {
      date_from: '2026-09-02T00:00:00Z',
      date_to: '2026-09-02T12:00:00Z',
    })

    expect(days.map((bucket) => bucket.day)).toEqual(['2026-09-01', '2026-09-02', '2026-09-03'])
  })

  it('ignores an unreadable or absurdly wide range and falls back to the data span', () => {
    expect(dailySeries([activity('2026-09-01')], { date_from: 'pas une date' })).toHaveLength(1)
    expect(dailySeries([activity('2026-09-01')], { date_from: '1970-01-01T00:00:00Z' })).toHaveLength(1)
  })

  it('returns nothing when there is no activity, whatever the range', () => {
    expect(dailySeries([], { date_from: '2026-09-01T00:00:00Z', date_to: '2026-09-30T00:00:00Z' })).toEqual([])
  })
})

describe('hasKnownTokens', () => {
  it('is false when every point has unknown tokens', () => {
    expect(hasKnownTokens([activity('2026-09-01', { input_tokens: null, output_tokens: null })])).toBe(false)
    expect(hasKnownTokens([activity('2026-09-01', { input_tokens: 0, output_tokens: null })])).toBe(true)
  })
})

function model(overrides: Partial<ModelPoint>): ModelPoint {
  return {
    label: 'model-a',
    model_id: 5,
    provider_name: 'provider',
    data_source_id: 1,
    call_count: 1,
    input_tokens: null,
    output_tokens: null,
    coverage: { present: 0, total: 1, ratio: 0 },
    cache_read_tokens: null,
    cache_coverage: { present: 0, total: 1, ratio: 0 },
    filters: { model_id: 5, data_source_id: 1 },
    ...overrides,
  }
}

describe('aggregateModels', () => {
  it('gives no drill-down to a model without id instead of opening the whole source', () => {
    const [unknown] = aggregateModels([model({ label: 'unknown', model_id: null, filters: { data_source_id: 1 } })])

    expect(unknown?.filters).toBeNull()
  })

  it('keeps the drill-down of a known model', () => {
    expect(aggregateModels([model({})])[0]?.filters).toEqual({ model_id: 5, data_source_id: 1 })
  })

  it('names the source only when asked, so one model in two sources reads as two rows', () => {
    const points = [model({ call_count: 3 }), model({ data_source_id: 2, filters: { model_id: 5, data_source_id: 2 } })]

    expect(aggregateModels(points).map((item) => item.label)).toEqual(['model-a', 'model-a'])
    const sources = [{ id: 1, name: 'TraceLab' }]
    expect(aggregateModels(points, { showSource: true, sources }).map((item) => item.label)).toEqual([
      'model-a · TraceLab',
      'model-a · Source 2',
    ])
  })
})

describe('aggregateTools', () => {
  it('names the source when asked and still keeps the limit', () => {
    const tool = (index: number): ToolPoint => ({
      label: `tool-${index}`,
      tool_id: index,
      data_source_id: 1,
      call_count: index,
      error_count: 0,
      error_ratio: null,
      coverage: { present: 0, total: 0, ratio: 0 },
      filters: { tool_id: index },
    })

    const items = aggregateTools([tool(1), tool(2), tool(3)], { showSource: true, sources: [], limit: 2 })

    // A source the API did not list is named by its id, never guessed.
    expect(items.map((item) => item.label)).toEqual(['tool-3 · Source 1', 'tool-2 · Source 1'])
  })
})
