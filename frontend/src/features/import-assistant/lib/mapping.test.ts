import { describe, expect, it } from 'vitest'

import { confidenceLabel, fieldConfidence } from '@/features/import-assistant/lib/mapping'

describe('confidenceLabel', () => {
  it.each(['high', 'medium', 'low'])('keeps the agent label %s as is', (label) => {
    expect(confidenceLabel(label)).toBe(label)
  })

  it('normalises case and spacing', () => {
    expect(confidenceLabel(' Medium ')).toBe('medium')
  })

  it.each([0.9, 90, 'very sure', '', undefined])('shows nothing for %s, rather than inventing a measure', (value) => {
    expect(confidenceLabel(value)).toBeUndefined()
  })
})

describe('fieldConfidence', () => {
  it('returns the label of the rationale that targets the field', () => {
    const rationale = [
      { target: 'session.external_id', confidence: 'low' },
      { target: 'session.model', confidence: 'high' },
    ]

    expect(fieldConfidence(rationale, 'session', 'model')).toBe('high')
    expect(fieldConfidence(rationale, 'session', 'started_at')).toBeUndefined()
  })
})
