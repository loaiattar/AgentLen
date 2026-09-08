import type { ComponentProps, ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'

export function Table({ className, ...props }: ComponentProps<'table'>) {
  return (
    <div data-slot="table-wrap" className="relative w-full overflow-x-auto">
      <table data-slot="table" className={cn('w-full caption-bottom text-secondary', className)} {...props} />
    </div>
  )
}

export function TableHeader({ className, ...props }: ComponentProps<'thead'>) {
  return <thead data-slot="table-header" className={cn('text-meta text-foreground-subtle', className)} {...props} />
}

export function TableBody({ className, ...props }: ComponentProps<'tbody'>) {
  return <tbody data-slot="table-body" className={cn('[&_tr:last-child]:border-0', className)} {...props} />
}

export function TableRow({ className, ...props }: ComponentProps<'tr'>) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        'border-b border-border transition-colors hover:bg-primary-soft/60 data-[state=selected]:bg-primary-soft',
        className,
      )}
      {...props}
    />
  )
}

export function TableHead({ className, ...props }: ComponentProps<'th'>) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        'h-10 px-3 text-left align-middle font-medium tracking-[0.12em] uppercase',
        className,
      )}
      {...props}
    />
  )
}

export function TableCell({ className, ...props }: ComponentProps<'td'>) {
  return <td data-slot="table-cell" className={cn('px-3 py-3 align-middle text-body', className)} {...props} />
}

export interface TableEmptyProps {
  children: ReactNode
}

export function TableEmpty({ children }: TableEmptyProps) {
  return (
    <TableRow>
      <TableCell colSpan={99} className="py-12 text-center text-foreground-muted">
        {children}
      </TableCell>
    </TableRow>
  )
}
