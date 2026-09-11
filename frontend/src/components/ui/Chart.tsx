import { useId, type ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'

const seriesColors = {
  cyan: 'var(--color-primary-emphasis)',
  blue: 'var(--color-accent-blue)',
  magenta: 'var(--color-accent-magenta)',
  mint: 'var(--color-accent-mint)',
  pink: 'var(--color-error)',
} as const

type SeriesTone = keyof typeof seriesColors

/** `null` is an unknown value: the line breaks there instead of dropping to 0. */
export type SeriesValue = number | null

export interface SeriesChartProps {
  /** One value per evenly spaced column, in order. */
  values: SeriesValue[]
  tone?: SeriesTone
  className?: string
  label: string
  /** One label per value; a few evenly spaced ones are drawn under the chart. */
  xLabels?: string[]
  /** Wraps the hit area over one column, e.g. in a link. */
  wrapColumn?: (index: number, content: ReactNode) => ReactNode
}

const AXIS_TICKS = 5

/** Center of column `index`: columns, hit areas and labels share this geometry. */
function columnX(index: number, count: number): number {
  return ((index + 0.5) / count) * 100
}

function tickIndices(count: number): number[] {
  if (count <= AXIS_TICKS) return Array.from({ length: count }, (_, index) => index)
  return [...new Set(Array.from({ length: AXIS_TICKS }, (_, tick) => Math.round((tick * (count - 1)) / (AXIS_TICKS - 1))))]
}

/** Consecutive known values, as `[index, value]` pairs. */
function knownRuns(values: SeriesValue[]): Array<Array<[number, number]>> {
  const runs: Array<Array<[number, number]>> = []
  let current: Array<[number, number]> = []
  values.forEach((value, index) => {
    if (value == null) {
      if (current.length > 0) runs.push(current)
      current = []
    } else {
      current.push([index, value])
    }
  })
  if (current.length > 0) runs.push(current)
  return runs
}

function SeriesLines({ values, stroke, y }: { values: SeriesValue[]; stroke: string; y: (value: number) => number }) {
  return knownRuns(values).map((run) => {
    const [head] = run
    const key = head?.[0]
    if (run.length === 1 && head) {
      // A lone known value between gaps: a dot, or it would not be drawn at all.
      const x = columnX(head[0], values.length)
      return (
        <line key={key} x1={x} x2={x} y1={y(head[1])} y2={y(head[1])} stroke={stroke} strokeWidth="4" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      )
    }
    return (
      <polyline
        key={key}
        fill="none"
        stroke={stroke}
        strokeWidth="1.4"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={run.map(([index, value]) => `${columnX(index, values.length)},${y(value)}`).join(' ')}
        vectorEffect="non-scaling-stroke"
      />
    )
  })
}

function SeriesFrame({
  count,
  className,
  xLabels,
  wrapColumn,
  children,
}: Pick<SeriesChartProps, 'className' | 'xLabels' | 'wrapColumn'> & { count: number; children: ReactNode }) {
  const ticks = xLabels && xLabels.length === count ? tickIndices(count) : []

  return (
    <div className={cn('flex w-full flex-col', className)}>
      <div className="relative min-h-0 flex-1">
        {children}
        {wrapColumn ? (
          <div className="absolute inset-0 flex">
            {Array.from({ length: count }, (_, index) => (
              <div key={index} className="flex min-w-0 flex-1">
                {wrapColumn(index, <span className="block size-full" />)}
              </div>
            ))}
          </div>
        ) : null}
      </div>
      {ticks.length > 0 ? (
        <div aria-hidden="true" className="relative mt-2 h-4 shrink-0 text-meta text-foreground-subtle">
          {ticks.map((index) => {
            const x = columnX(index, count)
            const position = x < 10 ? { left: 0 } : x > 90 ? { right: 0 } : { left: `${x}%`, transform: 'translateX(-50%)' }
            return (
              <span key={index} className="absolute top-0 whitespace-nowrap" style={position}>
                {xLabels?.[index]}
              </span>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}

export type SparklineProps = SeriesChartProps

export function Sparkline({ values, tone = 'cyan', className, label, xLabels, wrapColumn }: SparklineProps) {
  const known = values.filter((value): value is number => value != null)
  const max = Math.max(...known, 1)
  const min = Math.min(...known, 0)
  const range = max - min || 1

  return (
    <SeriesFrame count={values.length} className={cn('h-24', className)} xLabels={xLabels} wrapColumn={wrapColumn}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 size-full" aria-label={label} role="img">
        <SeriesLines values={values} stroke={seriesColors[tone]} y={(value) => 96 - ((value - min) / range) * 92} />
      </svg>
    </SeriesFrame>
  )
}

export type AreaChartProps = SeriesChartProps

export function AreaChart({ values, tone = 'cyan', className, label, xLabels, wrapColumn }: AreaChartProps) {
  const gradientId = `area-${useId().replace(/:/g, '')}`
  const max = Math.max(...values.filter((value): value is number => value != null), 1)
  const y = (value: number) => 100 - (value / max) * 86

  return (
    <SeriesFrame count={values.length} className={cn('h-full', className)} xLabels={xLabels} wrapColumn={wrapColumn}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 size-full" aria-label={label} role="img">
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={seriesColors[tone]} stopOpacity="0.35" />
            <stop offset="100%" stopColor={seriesColors[tone]} stopOpacity="0" />
          </linearGradient>
        </defs>
        {knownRuns(values)
          .filter((run) => run.length > 1)
          .map((run) => {
            const line = run.map(([index, value]) => `${columnX(index, values.length)},${y(value)}`).join(' ')
            const firstX = columnX(run[0]?.[0] ?? 0, values.length)
            const lastX = columnX(run.at(-1)?.[0] ?? 0, values.length)
            return <polygon key={run[0]?.[0]} fill={`url(#${gradientId})`} points={`${firstX},100 ${line} ${lastX},100`} />
          })}
        <SeriesLines values={values} stroke={seriesColors[tone]} y={y} />
      </svg>
    </SeriesFrame>
  )
}

export interface BarRow {
  label: string
  value: number
  tone?: SeriesTone
}

export interface BarListProps<T extends BarRow = BarRow> {
  items: T[]
  className?: string
  wrapItem?: (item: T, content: ReactNode) => ReactNode
}

export function BarList<T extends BarRow>({ items, className, wrapItem }: BarListProps<T>) {
  const max = Math.max(...items.map((item) => item.value), 1)

  return (
    <ul className={cn('grid gap-4', className)}>
      {items.map((item, index) => {
        const content = (
          <>
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
          </>
        )

        return (
          <li key={`${item.label}-${index}`} className="grid gap-1.5">
            {wrapItem ? wrapItem(item, content) : content}
          </li>
        )
      })}
    </ul>
  )
}

export interface MixSlice {
  label: string
  value: number
  tone: SeriesTone
}

export interface MixLegendProps<T extends MixSlice = MixSlice> {
  items: T[]
  className?: string
  wrapItem?: (item: T, content: ReactNode) => ReactNode
}

export function MixLegend<T extends MixSlice>({ items, className, wrapItem }: MixLegendProps<T>) {
  const total = items.reduce((sum, item) => sum + item.value, 0) || 1

  return (
    <div className={cn('flex h-full flex-col justify-between gap-6', className)}>
      <div className="flex h-2 overflow-hidden rounded-pill">
        {items.map((item, index) => (
          <div
            key={`${item.label}-${index}`}
            style={{ width: `${(item.value / total) * 100}%`, background: seriesColors[item.tone] }}
          />
        ))}
      </div>
      <ul className="grid gap-3">
        {items.map((item, index) => {
          const content = (
            <>
              <span className="flex items-center gap-2 text-foreground-muted">
                <span className="size-1.5 rounded-full" style={{ background: seriesColors[item.tone] }} />
                {item.label}
              </span>
              <span className="text-foreground">{Math.round((item.value / total) * 100)}%</span>
            </>
          )

          return (
            <li key={`${item.label}-${index}`} className="flex items-center justify-between gap-3 text-secondary">
              {wrapItem ? wrapItem(item, content) : content}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
