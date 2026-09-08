import type { ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'

export interface EmptyStateProps {
  title: string
  description: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div
      data-slot="empty-state"
      className={cn(
        'glass-surface flex min-h-72 flex-col items-start justify-end rounded-xl p-8 md:min-h-80 md:p-10',
        className,
      )}
    >
      <h2 className="font-display text-hero text-foreground">{title}</h2>
      <p className="mt-3 max-w-md text-body text-foreground-muted">{description}</p>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  )
}
