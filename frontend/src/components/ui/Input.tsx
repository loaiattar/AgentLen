import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils/cn'

export interface InputProps extends ComponentProps<'input'> {
  error?: boolean
}

export function Input({ className, error, type = 'text', ...props }: InputProps) {
  return (
    <input
      type={type}
      data-slot="input"
      data-error={error || undefined}
      aria-invalid={error || undefined}
      className={cn(
        'h-9 w-full rounded-md border border-border bg-glass-soft px-3 text-body text-foreground shadow-none outline-none transition-[border,background,box-shadow] duration-[var(--duration-fast)]',
        'placeholder:text-foreground-subtle',
        'hover:border-border-strong hover:bg-glass',
        'focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary-emphasis/50',
        'disabled:cursor-not-allowed disabled:opacity-40',
        'data-[error=true]:border-error data-[error=true]:bg-error-soft data-[error=true]:focus-visible:ring-error/40',
        className,
      )}
      {...props}
    />
  )
}
