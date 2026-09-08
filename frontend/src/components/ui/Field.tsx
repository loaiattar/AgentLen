import type { ComponentProps, ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'

export interface FieldProps extends ComponentProps<'div'> {
  label: string
  htmlFor?: string
  hint?: ReactNode
  error?: string
  children: ReactNode
}

export function Field({ label, htmlFor, hint, error, className, children, ...props }: FieldProps) {
  return (
    <div data-slot="field" data-error={Boolean(error) || undefined} className={cn('grid gap-1.5', className)} {...props}>
      <label htmlFor={htmlFor} className="text-meta font-medium tracking-wide text-foreground-muted uppercase">
        {label}
      </label>
      {children}
      {error ? (
        <p role="alert" className="text-secondary text-error">
          {error}
        </p>
      ) : hint ? (
        <p className="text-secondary text-foreground-subtle">{hint}</p>
      ) : null}
    </div>
  )
}
