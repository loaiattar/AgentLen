import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils/cn'

export interface SkeletonProps extends ComponentProps<'div'> {
  label?: string
}

export function Skeleton({ className, label = 'Loading', ...props }: SkeletonProps) {
  return (
    <div
      data-slot="skeleton"
      role="status"
      aria-label={label}
      className={cn('skeleton-shimmer rounded-md bg-glass-soft', className)}
      {...props}
    />
  )
}

export function GlassSkeleton({ className, ...props }: SkeletonProps) {
  return (
    <div data-slot="glass-skeleton" className={cn('glass-surface rounded-xl p-6', className)} {...props}>
      <Skeleton className="h-3 w-24" />
      <Skeleton className="mt-6 h-10 w-32" />
      <Skeleton className="mt-4 h-3 w-20" />
    </div>
  )
}
