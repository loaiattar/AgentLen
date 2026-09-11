import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AreaChart, Sparkline } from '@/components/ui/Chart'

describe('Sparkline', () => {
  it('breaks the line at an unknown value instead of drawing it as 0', () => {
    const { container } = render(<Sparkline values={[1, 2, null, 4, 5]} label="Tokens" />)

    expect(container.querySelectorAll('polyline')).toHaveLength(2)
  })

  it('draws a lone known value between gaps as a dot', () => {
    const { container } = render(<Sparkline values={[null, 3, null]} label="Tokens" />)

    expect(container.querySelectorAll('polyline')).toHaveLength(0)
    expect(container.querySelectorAll('line')).toHaveLength(1)
  })
})

describe('AreaChart', () => {
  it('labels a few evenly spaced days, first and last included', () => {
    const labels = Array.from({ length: 10 }, (_, index) => `day ${index}`)

    render(<AreaChart values={labels.map(() => 1)} xLabels={labels} label="Sessions" />)

    expect(screen.getByText('day 0')).toBeInTheDocument()
    expect(screen.getByText('day 9')).toBeInTheDocument()
    expect(screen.queryAllByText(/^day \d$/)).toHaveLength(5)
  })

  it('draws no labels when they do not match the values one to one', () => {
    render(<AreaChart values={[1, 2, 3]} xLabels={['only one']} label="Sessions" />)

    expect(screen.queryByText('only one')).not.toBeInTheDocument()
  })

  it('offers one hit area per value, left to the caller to wrap', () => {
    render(
      <AreaChart
        values={[1, 0, 2]}
        label="Sessions"
        wrapColumn={(index, content) =>
          index === 1 ? content : (
            <a href={`#${index}`} aria-label={`column ${index}`}>
              {content}
            </a>
          )
        }
      />,
    )

    expect(screen.getAllByRole('link').map((link) => link.getAttribute('aria-label'))).toEqual(['column 0', 'column 2'])
  })
})
