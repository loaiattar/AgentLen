import type { ComponentProps, ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'

export interface KpiProps extends ComponentProps<'div'> {
  label: string
  value: ReactNode
  delta?: string
  deltaTone?: 'positive' | 'negative' | 'neutral'
  hint?: string
}

export function Kpi({
  label,
  value,
  delta,
  deltaTone = 'neutral',
  hint,
  className,
  ...props
}: KpiProps) {
  return (
    <div data-slot="kpi" className={cn('flex h-full min-h-36 flex-col justify-between p-6', className)} {...props}>
      <p className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">{label}</p>
      <div>
        <p className="font-display text-kpi text-foreground">{value}</p>
        {delta ? (
          <p
            className={cn(
              'mt-2 text-secondary',
              deltaTone === 'positive' && 'text-primary',
              deltaTone === 'negative' && 'text-error',
              deltaTone === 'neutral' && 'text-foreground-muted',
            )}
          >
            {delta}
          </p>
        ) : null}
        {hint ? <p className="mt-1 text-secondary text-foreground-subtle">{hint}</p> : null}
      </div>
    </div>
  )
}
