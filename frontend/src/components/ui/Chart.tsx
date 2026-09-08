import { useId } from 'react'

import { cn } from '@/lib/utils/cn'

const seriesColors = {
  cyan: 'var(--color-primary-emphasis)',
  blue: 'var(--color-accent-blue)',
  magenta: 'var(--color-accent-magenta)',
  mint: 'var(--color-accent-mint)',
  pink: 'var(--color-error)',
} as const

type SeriesTone = keyof typeof seriesColors

export interface SparklineProps {
  values: number[]
  tone?: SeriesTone
  className?: string
  label: string
}

export function Sparkline({ values, tone = 'cyan', className, label }: SparklineProps) {
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const range = max - min || 1
  const points = values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * 100
      const y = 100 - ((value - min) / range) * 100
      return `${x},${y}`
    })
    .join(' ')

  return (
    <svg viewBox="0 0 100 36" preserveAspectRatio="none" className={cn('h-24 w-full', className)} aria-label={label} role="img">
      <polyline
        fill="none"
        stroke={seriesColors[tone]}
        strokeWidth="1.4"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={points}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

export interface AreaChartProps {
  values: number[]
  tone?: SeriesTone
  className?: string
  label: string
}

export function AreaChart({ values, tone = 'cyan', className, label }: AreaChartProps) {
  const gradientId = `area-${useId().replace(/:/g, '')}`
  const max = Math.max(...values, 1)
  const points = values.map((value, index) => {
    const x = (index / Math.max(values.length - 1, 1)) * 100
    const y = 100 - (value / max) * 86
    return `${x},${y}`
  })
  const line = points.join(' ')
  const area = `0,100 ${line} 100,100`

  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className={cn('h-full w-full', className)} aria-label={label} role="img">
      <defs>
        <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={seriesColors[tone]} stopOpacity="0.35" />
          <stop offset="100%" stopColor={seriesColors[tone]} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon fill={`url(#${gradientId})`} points={area} />
      <polyline
        fill="none"
        stroke={seriesColors[tone]}
        strokeWidth="1.2"
        points={line}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

export interface BarRow {
  label: string
  value: number
  tone?: SeriesTone
}

export interface BarListProps {
  items: BarRow[]
  className?: string
}

export function BarList({ items, className }: BarListProps) {
  const max = Math.max(...items.map((item) => item.value), 1)

  return (
    <ul className={cn('grid gap-4', className)}>
      {items.map((item) => (
        <li key={item.label} className="grid gap-1.5">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-secondary text-foreground-muted">{item.label}</span>
            <span className="text-meta text-foreground">{item.value}</span>
          </div>
          <div className="h-1 overflow-hidden rounded-pill bg-surface-sunken">
            <div
              className="h-full rounded-pill"
              style={{
                width: `${(item.value / max) * 100}%`,
                background: seriesColors[item.tone ?? 'cyan'],
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

export interface MixSlice {
  label: string
  value: number
  tone: SeriesTone
}

export interface MixLegendProps {
  items: MixSlice[]
  className?: string
}

export function MixLegend({ items, className }: MixLegendProps) {
  const total = items.reduce((sum, item) => sum + item.value, 0) || 1

  return (
    <div className={cn('flex h-full flex-col justify-between gap-6', className)}>
      <div className="flex h-2 overflow-hidden rounded-pill">
        {items.map((item) => (
          <div
            key={item.label}
            style={{ width: `${(item.value / total) * 100}%`, background: seriesColors[item.tone] }}
          />
        ))}
      </div>
      <ul className="grid gap-3">
        {items.map((item) => (
          <li key={item.label} className="flex items-center justify-between gap-3 text-secondary">
            <span className="flex items-center gap-2 text-foreground-muted">
              <span className="size-1.5 rounded-full" style={{ background: seriesColors[item.tone] }} />
              {item.label}
            </span>
            <span className="text-foreground">{Math.round((item.value / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
