import { BentoGrid, BentoModule } from '@/components/ui/Bento'

const steps = [
  {
    index: '01',
    title: 'Import',
    body: 'Drop JSONL, CSV or Parquet. Fields are profiled, never rewritten in place.',
  },
  {
    index: '02',
    title: 'Normalize',
    body: 'A mapping — human or AI-assisted — lands traces in one relational model.',
  },
  {
    index: '03',
    title: 'Explore',
    body: 'Sessions, tokens, tools and quality, side by side in the same window.',
  },
]

export function HowItWorks() {
  return (
    <section className="grid gap-[var(--space-3)]">
      <div data-reveal="section">
        <p className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">
          Flow
        </p>
        <h2 className="mt-[var(--space-1)] font-display text-section text-foreground">
          Import → Normalize → Explore
        </h2>
      </div>
      <BentoGrid>
        {steps.map((step) => (
          <BentoModule
            key={step.index}
            cols={2}
            interactive
            className="flex min-h-48 flex-col justify-between"
            data-reveal="module"
          >
            <p className="font-display text-kpi text-foreground-subtle">{step.index}</p>
            <div>
              <h3 className="text-card text-foreground">{step.title}</h3>
              <p className="mt-[var(--space-1)] text-body text-foreground-muted">{step.body}</p>
            </div>
          </BentoModule>
        ))}
      </BentoGrid>
    </section>
  )
}
