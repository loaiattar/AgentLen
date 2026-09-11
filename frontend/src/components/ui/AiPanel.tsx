import type { ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'
import { Badge } from '@/components/ui/Badge'

export interface AiInsight {
  title: string
  body: string
  /** The label the agent gave (high, medium, low) — never a computed percentage. */
  confidence?: string
  tone?: 'info' | 'warning' | 'success'
}

export interface AiPanelProps {
  title?: string
  insights: AiInsight[]
  footer?: ReactNode
  className?: string
}

/** A warning (validation failed, ambiguity) must not read like an explanation. */
const TONE_CLASSES: Record<NonNullable<AiInsight['tone']>, string> = {
  info: '',
  warning: 'rounded-lg bg-warning-soft p-3',
  success: 'rounded-lg bg-success-soft p-3',
}

export function AiPanel({ title = 'Assistant', insights, footer, className }: AiPanelProps) {
  return (
    <aside data-slot="ai-panel" className={cn('glass-module flex h-full flex-col p-6', className)}>
      <div className="mb-6 flex items-center justify-between gap-3">
        <h2 className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">{title}</h2>
        <Badge tone="magenta">AI</Badge>
      </div>
      <ul className="grid flex-1 gap-5">
        {insights.map((insight, index) => {
          const tone = insight.tone ?? 'info'
          return (
            // Titles repeat: a field can be both ambiguous and unmapped.
            <li key={`${index}-${insight.title}`} data-tone={tone} className={cn('grid gap-1.5', TONE_CLASSES[tone])}>
              <p className="text-card text-foreground">{insight.title}</p>
              <p className="text-secondary text-foreground-muted">{insight.body}</p>
              {insight.confidence != null ? (
                <p className="text-meta text-accent-magenta">Confidence: {insight.confidence}</p>
              ) : null}
            </li>
          )
        })}
      </ul>
      {footer ? <div className="mt-6">{footer}</div> : null}
    </aside>
  )
}
