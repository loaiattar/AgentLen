import type { ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'

export interface PageHeaderProps {
  title: string
  action?: ReactNode
  className?: string
}

export function PageHeader({ title, action, className }: PageHeaderProps) {
  return (
    <header
      className={cn(
        'mb-[var(--space-4)] flex flex-col gap-[var(--space-3)] md:flex-row md:items-end md:justify-between',
        className,
      )}
    >
      <h1 className="font-display text-page text-foreground text-balance">{title}</h1>
      {action ? <div className="flex shrink-0 items-center gap-[var(--space-1)]">{action}</div> : null}
    </header>
  )
}
