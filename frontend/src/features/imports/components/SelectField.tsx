import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils/cn'

export interface SelectProps extends ComponentProps<'select'> {
  error?: boolean
}

/**
 * A native select styled to match `Input`. Deliberately not a Radix listbox:
 * the design system has no Select yet, and adding one is the design system's
 * call, not this feature's.
 */
export function Select({ className, error, ...props }: SelectProps) {
  return (
    <select
      data-slot="select"
      data-error={error || undefined}
      aria-invalid={error || undefined}
      className={cn(
        'h-9 w-full rounded-md border border-border bg-glass-soft px-3 text-body text-foreground outline-none transition-[border,background,box-shadow] duration-[var(--duration-fast)]',
        'hover:border-border-strong hover:bg-glass',
        'focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary-emphasis/50',
        'disabled:cursor-not-allowed disabled:opacity-40',
        'data-[error=true]:border-error data-[error=true]:bg-error-soft',
        className,
      )}
      {...props}
    />
  )
}
