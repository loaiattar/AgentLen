import type { ComponentProps } from 'react'
import { type VariantProps } from 'class-variance-authority'

import { statusDotVariants } from '@/components/ui/status-dot.variants'
import { cn } from '@/lib/utils/cn'

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
