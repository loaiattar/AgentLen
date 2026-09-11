import type { ComponentProps, ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'

export interface FilterBarProps extends ComponentProps<'div'> {
  children: ReactNode
}

export function FilterBar({ className, children, ...props }: FilterBarProps) {
  return (
    <div
      data-slot="filter-bar"
      className={cn(
        'glass-surface mb-6 flex flex-wrap items-center gap-2 rounded-xl px-3 py-2',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export interface FilterChipProps extends ComponentProps<'button'> {
  active?: boolean
}

export function FilterChip({ active, className, ...props }: FilterChipProps) {
  return (
    <button
      type="button"
      data-active={active || undefined}
      className={cn(
        'h-7 rounded-md px-2.5 text-secondary text-foreground-muted transition-colors',
        'hover:bg-primary-soft hover:text-foreground',
        'data-[active=true]:bg-primary-soft data-[active=true]:text-foreground',
        'focus-visible:ring-2 focus-visible:ring-primary-emphasis/70',
        className,
      )}
      {...props}
    />
  )
}
