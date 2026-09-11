import type { ComponentProps } from 'react'
import { type VariantProps } from 'class-variance-authority'

import { badgeVariants } from '@/components/ui/badge.variants'
import { cn } from '@/lib/utils/cn'

export interface BadgeProps extends ComponentProps<'span'>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span data-slot="badge" className={cn(badgeVariants({ tone, className }))} {...props} />
}
