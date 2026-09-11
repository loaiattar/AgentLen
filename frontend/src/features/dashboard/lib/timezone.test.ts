import { afterAll, describe, expect, it, vi } from 'vitest'

import type { ActivityPoint } from '@/features/dashboard/types'

// CI runs in UTC, where a day formatted in the local zone looks right by
// accident. New York is behind UTC: 00:00 UTC there is still the day before.
// Node applies a new `process.env.TZ` to later dates and formatters, so the
// modules are imported only once it is set: their formatters are built on load.
vi.stubEnv('TZ', 'America/New_York')
const { filterChipLabel } = await import('@/features/dashboard/lib/filters')
const { dailySeries, formatDay } = await import('@/features/dashboard/lib/format')

afterAll(() => {
  vi.unstubAllEnvs()
})

function activity(day: string): ActivityPoint {
  return {
    day,
    data_source_id: 1,
    session_count: 1,
    model_call_count: 0,
    tool_call_count: 0,
    input_tokens: null,
    output_tokens: null,
    coverage: { present: 0, total: 1, ratio: 0 },
    filters: { data_source_id: 1, date_from: `${day}T00:00:00+00:00`, date_to: `${day}T23:59:59+00:00` },
  }
}

describe('days outside UTC (America/New_York)', () => {
  it('really runs behind UTC', () => {
    expect(new Date('2026-09-01T00:00:00Z').getDate()).toBe(31)
  })

  it('formats a UTC day as that day, not the local day before', () => {
    expect(formatDay('2026-09-01')).toMatch(/^01 Sept?$/)
  })

  it('buckets a requested range by UTC day', () => {
    const days = dailySeries([activity('2026-09-01')], {
      date_from: '2026-08-31T20:00:00-04:00',
      date_to: '2026-09-02T23:59:59Z',
    })

    expect(days.map((bucket) => bucket.day)).toEqual(['2026-09-01', '2026-09-02'])
  })

  it('labels a date filter in UTC, like the day it was drilled from', () => {
    expect(filterChipLabel('date_from', '2026-09-01T00:00:00+00:00')).toMatch(/^From 01 Sept?,? 00:00 UTC$/)
  })
})
