import type { ComponentProps, ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'

type BentoCols = 1 | 2 | 3 | 4 | 6
type BentoRows = 1 | 2

const colClass: Record<BentoCols, string> = {
  1: 'col-span-1 md:col-span-1 xl:col-span-2',
  2: 'col-span-1 md:col-span-2 xl:col-span-4',
  3: 'col-span-1 md:col-span-3 xl:col-span-6',
  4: 'col-span-1 md:col-span-4 xl:col-span-8',
  6: 'col-span-1 md:col-span-6 xl:col-span-12',
}

export interface BentoGridProps extends ComponentProps<'div'> {}

export function BentoGrid({ className, ...props }: BentoGridProps) {
  return <div data-slot="bento-grid" className={cn('bento-grid', className)} {...props} />
}

export interface BentoModuleProps extends ComponentProps<'section'> {
  cols?: BentoCols
  rows?: BentoRows
  interactive?: boolean
  selected?: boolean
  padding?: 'none' | 'sm' | 'md'
  children: ReactNode
}

export function BentoModule({
  cols = 2,
  rows = 1,
  interactive = false,
  selected = false,
  padding = 'md',
  className,
  children,
  ...props
}: BentoModuleProps) {
  return (
    <section
      data-slot="bento-module"
      data-interactive={interactive || undefined}
      data-state={selected ? 'selected' : undefined}
      className={cn(
        'glass-module min-h-0',
        colClass[cols],
        rows === 2 && 'md:row-span-2',
        padding === 'sm' && 'p-4',
        padding === 'md' && 'p-6',
        padding === 'none' && 'p-0',
        className,
      )}
      {...props}
    >
      {children}
    </section>
  )
}

export interface BentoTitleProps {
  children: ReactNode
  className?: string
}

export function BentoTitle({ children, className }: BentoTitleProps) {
  return (
    <h2 className={cn('text-card font-medium text-foreground-muted', className)}>
      {children}
    </h2>
  )
}
