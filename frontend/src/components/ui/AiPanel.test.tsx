import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AiPanel } from '@/components/ui/AiPanel'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AiPanel', () => {
  it('shows the confidence label as given, never as a percentage', () => {
    render(<AiPanel insights={[{ title: 'session.external_id', body: 'from $.sid', confidence: 'high' }]} />)

    expect(screen.getByText('Confidence: high')).toBeInTheDocument()
    expect(screen.queryByText(/%/)).toBeNull()
  })

  it('styles an insight by its tone, so a warning does not read like an explanation', () => {
    render(
      <AiPanel
        insights={[
          { title: 'Validation failed', body: 'Unknown operator.', tone: 'warning' },
          { title: 'session.model', body: 'from $.model' },
        ]}
      />,
    )

    const [warning, info] = screen.getAllByRole('listitem')
    expect(warning).toHaveAttribute('data-tone', 'warning')
    expect(warning.className).toContain('bg-warning-soft')
    expect(info).toHaveAttribute('data-tone', 'info')
    expect(info.className).not.toContain('bg-warning-soft')
  })

  it('renders insights that share a title without a key collision', () => {
    // A field can be both ambiguous and unmapped: same title, two insights.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <AiPanel
        insights={[
          { title: '$.duration', body: 'Seconds or milliseconds?', tone: 'warning' },
          { title: '$.duration', body: 'Left unmapped.' },
        ]}
      />,
    )

    expect(screen.getAllByText('$.duration')).toHaveLength(2)
    const keyWarnings = consoleError.mock.calls.filter((args) => String(args[0]).includes('same key'))
    expect(keyWarnings).toHaveLength(0)
  })
})
