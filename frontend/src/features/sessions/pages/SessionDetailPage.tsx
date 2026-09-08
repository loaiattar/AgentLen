import { getRouteApi } from '@tanstack/react-router'

import { BentoGrid, BentoModule } from '@/components/ui/Bento'
import { Kpi } from '@/components/ui/Kpi'
import { PageHeader } from '@/components/ui/PageHeader'
import { Timeline, TimelineItem } from '@/components/ui/Timeline'

const routeApi = getRouteApi('/_app/sessions/$sessionId')

export function SessionDetailPage() {
  const { sessionId } = routeApi.useParams()

  return (
    <div>
      <PageHeader kicker="Session" title={sessionId} description="Forensic timeline of model, tool and system events." />
      <BentoGrid className="mb-8">
        <BentoModule cols={2} padding="none">
          <Kpi label="Duration" value="6m 04s" />
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi label="Tokens" value="182k" />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Tool calls" value="24" />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Errors" value="0" />
        </BentoModule>
        <BentoModule cols={2}>
          <p className="text-meta tracking-[0.14em] text-foreground-subtle uppercase">Model / agent</p>
          <p className="mt-4 font-display text-section text-foreground">gpt-4.1</p>
          <p className="mt-1 text-secondary text-foreground-muted">codegen</p>
        </BentoModule>
      </BentoGrid>
      <section className="glass-surface rounded-xl p-6 md:p-8">
        <h2 className="mb-6 text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">Timeline</h2>
        <Timeline>
          <TimelineItem time="00:00" tone="system" title="Session started" open />
          <TimelineItem time="00:04" tone="model" title="Model call · gpt-4.1" detail="1,204 prompt tokens" />
          <TimelineItem time="00:18" tone="tool" title="read_file · src/app/router.tsx" />
          <TimelineItem time="01:12" tone="agent" title="Agent planned a patch" />
          <TimelineItem time="02:40" tone="tool" title="apply_patch" detail="3 hunks" />
          <TimelineItem time="06:04" tone="system" title="Session completed" />
        </Timeline>
      </section>
    </div>
  )
}
