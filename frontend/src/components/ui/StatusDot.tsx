import type { ComponentProps } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils/cn'

const statusDotVariants = cva('inline-block size-1.5 shrink-0 rounded-full', {
  variants: {
    tone: {
      live: 'bg-primary-emphasis shadow-[0_0_8px_var(--color-primary-emphasis)]',
      success: 'bg-success',
      warning: 'bg-warning',
      error: 'bg-error',
      muted: 'bg-foreground-subtle',
      ai: 'bg-accent-magenta',
    },
  },
  defaultVariants: {
    tone: 'muted',
  },
})

export interface StatusDotProps extends ComponentProps<'span'>, VariantProps<typeof statusDotVariants> {
  label: string
}

export function StatusDot({ className, tone, label, ...props }: StatusDotProps) {
  return (
    <span
      data-slot="status-dot"
      role="img"
      aria-label={label}
      title={label}
      className={cn(statusDotVariants({ tone, className }))}
      {...props}
    />
  )
}

export { statusDotVariants }
