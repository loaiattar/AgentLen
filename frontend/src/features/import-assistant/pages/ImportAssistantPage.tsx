import { AiPanel } from '@/components/ui/AiPanel'
import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'

const fields = [
  { name: 'completion_tokens', sample: '1284', type: 'number' },
  { name: 'model_name', sample: 'gpt-4.1', type: 'string' },
  { name: 'tool_calls', sample: '[{…}]', type: 'json' },
  { name: 'latency_ms', sample: '1840', type: 'number' },
]

const mappings = [
  { from: 'completion_tokens', to: 'token_usage.completion', transform: 'numeric → integer', confidence: 92 },
  { from: 'model_name', to: 'model.name', transform: 'trim', confidence: 88 },
  { from: 'latency_ms', to: 'metrics.duration_ms', transform: 'none', confidence: 61 },
]

export function ImportAssistantPage() {
  return (
    <div>
      <PageHeader
        kicker="Import assistant"
        title="Mapping studio"
        description="The assistant proposes. You validate. The engine executes."
        action={<Button>Accept mapping</Button>}
      />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_minmax(18rem,0.9fr)]">
        <section className="glass-module p-6">
          <h2 className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">Dataset</h2>
          <ul className="mt-6 grid gap-5">
            {fields.map((field) => (
              <li key={field.name}>
                <p className="text-card text-foreground">{field.name}</p>
                <p className="text-secondary text-foreground-muted">
                  {field.type} · {field.sample}
                </p>
              </li>
            ))}
          </ul>
        </section>
        <section className="glass-module p-6">
          <h2 className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">Mapping</h2>
          <ul className="mt-6 grid gap-6">
            {mappings.map((mapping) => (
              <li key={mapping.from} className="grid gap-2">
                <p className="text-body text-foreground">{mapping.from}</p>
                <p className="text-secondary text-primary">↓ {mapping.to}</p>
                <p className="text-meta text-foreground-subtle">{mapping.transform}</p>
              </li>
            ))}
          </ul>
        </section>
        <AiPanel
          insights={[
            { title: '3 mappings require review', body: 'One field is ambiguous. Two are high confidence.' },
            {
              title: 'Likely mapping',
              body: 'completion_tokens aligns with token_usage.completion on name, type and sample range.',
              confidence: 82,
            },
            { title: 'Ambiguous field', body: 'latency_ms could be duration or time-to-first-token.' },
          ]}
        />
      </div>
    </div>
  )
}
