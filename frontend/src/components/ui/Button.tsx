import type { ComponentProps } from 'react'
import { Slot } from 'radix-ui'
import { type VariantProps } from 'class-variance-authority'
import { LoaderCircle } from 'lucide-react'

import { buttonVariants } from '@/components/ui/button.variants'
import { cn } from '@/lib/utils/cn'

export interface ButtonProps extends ComponentProps<'button'>, VariantProps<typeof buttonVariants> {
  asChild?: boolean
  loading?: boolean
}

export function Button({
  className,
  variant,
  size,
  asChild = false,
  loading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot.Root : 'button'
  const content = asChild ? (
    children
  ) : (
    <>
      {loading ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : null}
      {/* This wrapper exists only to dim the label while loading, but it also
          becomes the button's single flex item — so the base `items-center
          gap-2` stopped applying between a label and its icon, leaving e.g. the
          dataset chevron flush against the text and off the baseline. It
          carries the same flex properties so the spacing survives it. */}
      <span className={cn('inline-flex items-center gap-2', loading && 'opacity-70')}>{children}</span>
    </>
  )

  return (
    <Comp
      data-slot="button"
      data-loading={loading || undefined}
      data-disabled={disabled || undefined}
      disabled={asChild ? undefined : disabled || loading}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    >
      {content}
    </Comp>
  )
}
