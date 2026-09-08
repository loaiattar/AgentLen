import { BentoGrid, BentoModule, BentoTitle } from '@/components/ui/Bento'
import { Badge } from '@/components/ui/Badge'
import { PageHeader } from '@/components/ui/PageHeader'

const sources = [
  { name: 'TraceLab', status: 'connected', last: '08 Sep', records: '48.2k', sessions: '12.1k' },
  { name: 'SWE-chat', status: 'connected', last: '07 Sep', records: '19.4k', sessions: '4.8k' },
  { name: 'Trace Commons', status: 'idle', last: '02 Sep', records: '6.1k', sessions: '1.9k' },
  { name: 'Unknown datasets', status: 'review', last: '06 Sep', records: '—', sessions: '—' },
]

export function SourcesListPage() {
  return (
    <div>
      <PageHeader kicker="Data sources" title="Connected origins" />
      <BentoGrid>
        {sources.map((source) => (
          <BentoModule key={source.name} cols={2} interactive>
            <div className="flex items-start justify-between gap-3">
              <BentoTitle>{source.name}</BentoTitle>
              <Badge tone={source.status === 'connected' ? 'mint' : source.status === 'review' ? 'magenta' : 'neutral'}>
                {source.status}
              </Badge>
            </div>
            <dl className="mt-8 grid grid-cols-3 gap-4 text-secondary">
              <div>
                <dt className="text-foreground-subtle">Last import</dt>
                <dd className="mt-1 text-foreground">{source.last}</dd>
              </div>
              <div>
                <dt className="text-foreground-subtle">Records</dt>
                <dd className="mt-1 text-foreground">{source.records}</dd>
              </div>
              <div>
                <dt className="text-foreground-subtle">Sessions</dt>
                <dd className="mt-1 text-foreground">{source.sessions}</dd>
              </div>
            </dl>
          </BentoModule>
        ))}
      </BentoGrid>
    </div>
  )
}
