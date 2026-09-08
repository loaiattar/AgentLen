import type { ReactNode } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils/cn'

const timelineTone = cva('mt-1.5 size-2 shrink-0 rounded-full', {
  variants: {
    tone: {
      model: 'bg-accent-magenta',
      tool: 'bg-primary-emphasis',
      agent: 'bg-accent-blue',
      system: 'bg-foreground-subtle',
      error: 'bg-error',
    },
  },
  defaultVariants: {
    tone: 'system',
  },
})

export interface TimelineItemProps extends VariantProps<typeof timelineTone> {
  time: string
  title: string
  detail?: ReactNode
  open?: boolean
}

export function Timeline({ children, className }: { children: ReactNode; className?: string }) {
  return <ol data-slot="timeline" className={cn('grid gap-0', className)}>{children}</ol>
}

export function TimelineItem({ time, title, detail, tone, open = false }: TimelineItemProps) {
  return (
    <li className="grid grid-cols-[1rem_1fr] gap-x-4">
      <div className="flex flex-col items-center">
        <span className={timelineTone({ tone })} />
        <span className="w-px flex-1 bg-border" />
      </div>
      <details className="group pb-6" open={open}>
        <summary className="flex cursor-pointer list-none items-baseline justify-between gap-4 [&::-webkit-details-marker]:hidden">
          <span className="text-body text-foreground">{title}</span>
          <time className="text-meta text-foreground-subtle">{time}</time>
        </summary>
        {detail ? <div className="mt-2 text-secondary text-foreground-muted">{detail}</div> : null}
      </details>
    </li>
  )
}
