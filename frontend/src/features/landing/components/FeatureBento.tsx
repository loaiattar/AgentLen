import { BentoGrid, BentoModule, BentoTitle } from '@/components/ui/Bento'

const features = [
  {
    title: 'Session exploration',
    body: 'Open any trace as a readable timeline of model and tool calls.',
    cols: 3 as const,
    rows: 2 as const,
  },
  {
    title: 'Tokens & models',
    body: 'Volume, mix and coverage. Missing values stay missing.',
    cols: 3 as const,
    rows: 1 as const,
  },
  {
    title: 'Tool calls',
    body: 'Usage and failure rates, ready to drill down.',
    cols: 3 as const,
    rows: 1 as const,
  },
  {
    title: 'Import & normalize',
    body: 'JSONL, CSV or Parquet into one shared relational model.',
    cols: 2 as const,
    rows: 1 as const,
  },
  {
    title: 'AI mapping',
    body: 'An assistant proposes field mappings. You accept.',
    cols: 2 as const,
    rows: 1 as const,
  },
  {
    title: 'Data quality',
    body: 'Rejections, duplicates and gaps — explained, never hidden.',
    cols: 2 as const,
    rows: 1 as const,
  },
]

export function FeatureBento() {
  return (
    <section className="grid gap-[var(--space-3)]">
      <div data-reveal="section">
        <p className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">
          Capabilities
        </p>
        <h2 className="mt-[var(--space-1)] font-display text-section text-foreground">
          Everything the dashboard already shows
        </h2>
      </div>
      <BentoGrid>
        {features.map((feature) => (
          <BentoModule
            key={feature.title}
            cols={feature.cols}
            rows={feature.rows}
            interactive
            className="flex min-h-36 flex-col justify-between"
            data-reveal="module"
          >
            <BentoTitle>{feature.title}</BentoTitle>
            <p className="mt-[var(--space-2)] max-w-sm text-body text-foreground">{feature.body}</p>
          </BentoModule>
        ))}
      </BentoGrid>
    </section>
  )
}
