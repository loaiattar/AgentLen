import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils/cn'

export interface TextareaProps extends ComponentProps<'textarea'> {
  error?: boolean
}

export function Textarea({ className, error, ...props }: TextareaProps) {
  return (
    <textarea
      data-slot="textarea"
      data-error={error || undefined}
      aria-invalid={error || undefined}
      className={cn(
        'min-h-24 w-full rounded-md border border-border bg-glass-soft px-3 py-2 text-body text-foreground outline-none transition-[border,background,box-shadow]',
        'placeholder:text-foreground-subtle',
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
