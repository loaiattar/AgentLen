import { Badge } from '@/components/ui/Badge'
import type { ImportPreview } from '@/features/import-assistant/types'

export interface PreviewPanelProps {
  preview: ImportPreview
}

export function PreviewPanel({ preview }: PreviewPanelProps) {
  return (
    <section className="glass-surface mt-[var(--space-3)] rounded-xl p-6">
      <h2 className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">Preview</h2>
      <p className="mt-3 text-body text-foreground">
        Sampled {preview.sampled} · would reject {preview.would_reject}
      </p>
      <ul className="mt-4 grid gap-2 text-secondary text-foreground-muted">
        {Object.entries(preview.would_import).map(([target, count]) => (
          <li key={target}>
            {target} · {count}
          </li>
        ))}
      </ul>
      {preview.issues.length > 0 ? (
        <ul className="mt-4 grid gap-2">
          {preview.issues.map((issue, index) => (
            <li key={`${issue.code}-${index}`}>
              <Badge tone={issue.severity === 'rejected' ? 'pink' : 'warning'}>{issue.code}</Badge>
              <span className="ml-2 text-secondary text-foreground-muted">{issue.message}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
