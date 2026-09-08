import type { ComponentProps } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils/cn'

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-pill px-2.5 py-0.5 text-meta font-medium tracking-wide',
  {
    variants: {
      tone: {
        neutral: 'bg-surface-sunken text-foreground-muted',
        cyan: 'bg-primary-soft text-primary',
        mint: 'bg-success-soft text-foreground',
        magenta: 'bg-accent-magenta-soft text-foreground',
        pink: 'bg-error-soft text-foreground',
        blue: 'bg-info-soft text-foreground',
        warning: 'bg-warning-soft text-foreground',
      },
    },
    defaultVariants: {
      tone: 'neutral',
    },
  },
)

export interface BadgeProps extends ComponentProps<'span'>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span data-slot="badge" className={cn(badgeVariants({ tone, className }))} {...props} />
}

export { badgeVariants }
