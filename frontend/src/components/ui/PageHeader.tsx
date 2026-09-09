import type { ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'

export interface PageHeaderProps {
  kicker?: string
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function PageHeader({ kicker, title, description, action, className }: PageHeaderProps) {
  return (
    <header
      className={cn(
        'mb-[var(--space-4)] flex flex-col gap-[var(--space-3)] md:flex-row md:items-end md:justify-between',
        className,
      )}
    >
      <div className="max-w-2xl">
        {kicker ? <p className="mb-[var(--space-1)] text-meta text-foreground-subtle uppercase">{kicker}</p> : null}
        <h1 className="font-display text-page text-foreground text-balance">{title}</h1>
        {description ? (
          <p className="mt-[var(--space-1)] max-w-xl text-body text-foreground-muted">{description}</p>
        ) : null}
      </div>
      {action ? <div className="flex shrink-0 items-center gap-[var(--space-1)]">{action}</div> : null}
    </header>
  )
}
