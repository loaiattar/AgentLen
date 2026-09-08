import type { ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'
import { Badge } from '@/components/ui/Badge'

export interface AiInsight {
  title: string
  body: string
  confidence?: number
  tone?: 'info' | 'warning' | 'success'
}

export interface AiPanelProps {
  title?: string
  insights: AiInsight[]
  footer?: ReactNode
  className?: string
}

export function AiPanel({ title = 'Assistant', insights, footer, className }: AiPanelProps) {
  return (
    <aside data-slot="ai-panel" className={cn('glass-module flex h-full flex-col p-6', className)}>
      <div className="mb-6 flex items-center justify-between gap-3">
        <h2 className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">{title}</h2>
        <Badge tone="magenta">AI</Badge>
      </div>
      <ul className="grid flex-1 gap-5">
        {insights.map((insight) => (
          <li key={insight.title} className="grid gap-1.5">
            <p className="text-card text-foreground">{insight.title}</p>
            <p className="text-secondary text-foreground-muted">{insight.body}</p>
            {insight.confidence != null ? (
              <p className="text-meta text-accent-magenta">Confidence {insight.confidence}%</p>
            ) : null}
          </li>
        ))}
      </ul>
      {footer ? <div className="mt-6">{footer}</div> : null}
    </aside>
  )
}
