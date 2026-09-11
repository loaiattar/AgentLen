import { Badge } from '@/components/ui/Badge'
import { BentoGrid, BentoModule, BentoTitle } from '@/components/ui/Bento'
import { StatusDot } from '@/components/ui/StatusDot'

const insights = [
  {
    title: 'session.external_id ← $.session_id',
    body: 'Unique on every sampled record.',
    confidence: 96,
  },
  {
    title: 'Duration unit is ambiguous',
    body: 'Seconds or milliseconds? Preview before you accept.',
    confidence: 61,
  },
  {
    title: '$.debug_flags has no target',
    body: 'Left unmapped. Nothing is invented.',
  },
]

export function AssistantSpotlight() {
  return (
    <section className="grid gap-[var(--space-3)]">
      <div data-reveal="section">
        <p className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">
          Import assistant
        </p>
        <h2 className="mt-[var(--space-1)] font-display text-section text-foreground">
          AI proposes. You decide.
        </h2>
      </div>
      <BentoGrid>
        <BentoModule cols={3} rows={2} className="flex min-h-64 flex-col justify-between" data-reveal="module">
          <div>
            <BentoTitle>Mapping without guesswork</BentoTitle>
            <p className="mt-[var(--space-3)] max-w-md text-body text-foreground">
              The assistant reads a sample, profiles fields, and suggests a mapping. It never writes
              to the database. You preview, correct, then import.
            </p>
          </div>
          <p className="flex items-center gap-[var(--space-1)] text-secondary text-foreground-muted">
            <StatusDot tone="ai" label="Assistant proposes only" />
            Proposes, never writes
          </p>
        </BentoModule>
        <BentoModule cols={3} rows={2} className="flex min-h-64 flex-col" data-reveal="module">
          <div className="mb-[var(--space-3)] flex items-center justify-between gap-[var(--space-1)]">
            <BentoTitle>Assistant</BentoTitle>
            <Badge tone="magenta">AI</Badge>
          </div>
          <ul className="grid flex-1 gap-[var(--space-3)]">
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
        </BentoModule>
      </BentoGrid>
    </section>
  )
}
