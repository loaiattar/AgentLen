import { describe, expect, it } from 'vitest'

import {
  formatBytes,
  formatCount,
  formatDateTime,
  formatExample,
  formatRatio,
  severityTone,
  statusTone,
  summarizeCounts,
  totalCount,
} from '@/features/imports/lib/format'

describe('formatRatio', () => {
  it('keeps decimals at both ends, not just the low one', () => {
    // The bug this pins: at 0 decimals, a `null_ratio` of 0.996 rendered
    // "100%" — "this column is entirely empty" for a column that has values.
    // `distinct_ratio` was worse: 0.996 read as a unique key.
    expect(formatRatio(0.996)).toBe('99.60%')
    expect(formatRatio(0.004)).toBe('0.40%')
  })

  it('keeps exact 0 and exact 1 clean, which is the whole point of the reading', () => {
    expect(formatRatio(0)).toBe('0%')
    expect(formatRatio(1)).toBe('100%')
  })

  it('stays terse in the middle of the range', () => {
    expect(formatRatio(0.5)).toBe('50%')
    expect(formatRatio(0.42)).toBe('42%')
  })

  it('distinguishes an absent ratio from zero (ARCHITECTURE §2)', () => {
    expect(formatRatio(null)).toBe('—')
    expect(formatRatio(undefined)).toBe('—')
    expect(formatRatio(0)).toBe('0%')
  })
})

describe('formatCount', () => {
  it('distinguishes an absent count from zero', () => {
    expect(formatCount(null)).toBe('—')
    expect(formatCount(undefined)).toBe('—')
    expect(formatCount(0)).toBe('0')
  })

  it('groups thousands', () => {
    expect(formatCount(1234567)).toBe('1,234,567')
  })
})

describe('formatBytes', () => {
  it('shows no decimal for bytes and one above', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(1024)).toBe('1.0 KB')
    expect(formatBytes(1536)).toBe('1.5 KB')
  })

  it('stops at the largest unit it knows rather than inventing one', () => {
    expect(formatBytes(1024 ** 5)).toContain('TB')
  })
})

describe('formatDateTime', () => {
  it('refuses a date it cannot read instead of showing "Invalid Date"', () => {
    expect(formatDateTime('pas une date')).toBe('—')
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime('')).toBe('—')
  })

  it('renders a real timestamp', () => {
    expect(formatDateTime('2026-09-11T08:30:00Z')).toMatch(/11 Sep/)
  })
})

describe('tones', () => {
  it('maps every run status, and falls back rather than crashing on an unknown one', () => {
    expect(statusTone('succeeded').dot).toBe('success')
    expect(statusTone('partial').badge).toBe('warning')
    // The API is free to add a status; the UI must not blow up when it does.
    expect(statusTone('something_new' as never)).toEqual(statusTone('pending'))
  })

  it('maps every severity, with a neutral fallback', () => {
    expect(severityTone('rejected')).toBe('pink')
    expect(severityTone('inconnue' as never)).toBe('neutral')
  })
})

describe('counts and formatExample', () => {
  it('sums a counts map, and answers 0 for an empty one', () => {
    expect(totalCount({ session: 20, model_call: 143 })).toBe(163)
    expect(totalCount({})).toBe(0)
  })

  it('summarizes a counts map, and says so when there is nothing', () => {
    expect(summarizeCounts({ session: 20, model_call: 1430 })).toBe(
      'session 20 · model_call 1,430',
    )
    expect(summarizeCounts({})).toBe('—')
  })

  it('renders a cell value without letting an object become "[object Object]"', () => {
    expect(formatExample(null)).toBe('—')
    expect(formatExample(undefined)).toBe('—')
    expect(formatExample('texte')).toBe('texte')
    expect(formatExample(42)).toBe('42')
    expect(formatExample({ nested: true })).toContain('nested')
  })
})
