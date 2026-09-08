import { Link } from '@tanstack/react-router'

import { AreaChart, BarList, MixLegend, Sparkline } from '@/components/ui/Chart'
import { BentoGrid, BentoModule, BentoTitle } from '@/components/ui/Bento'
import { Kpi } from '@/components/ui/Kpi'
import { PageHeader } from '@/components/ui/PageHeader'

const activity = [18, 22, 19, 28, 34, 31, 44, 41, 48, 52, 47, 61]
const tokens = [12, 14, 13, 18, 22, 19, 24, 28, 26, 31, 29, 36]
const tools = [
  { label: 'read_file', value: 1284, tone: 'cyan' as const },
  { label: 'shell', value: 842, tone: 'blue' as const },
  { label: 'grep', value: 611, tone: 'mint' as const },
  { label: 'apply_patch', value: 390, tone: 'magenta' as const },
]
const models = [
  { label: 'gpt-4.1', value: 54, tone: 'cyan' as const },
  { label: 'claude-sonnet', value: 28, tone: 'magenta' as const },
  { label: 'gemini', value: 18, tone: 'blue' as const },
]

export function DashboardPage() {
  return (
    <div>
      <PageHeader kicker="Overview" title="Agent activity" description="A calm window into traces, tokens and failures." />
      <BentoGrid>
        <BentoModule cols={2} rows={2} className="flex min-h-72 flex-col justify-between xl:min-h-80">
          <BentoTitle>Agent activity</BentoTitle>
          <AreaChart values={activity} label="Sessions over the last twelve intervals" className="mt-6 h-44" />
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi label="Total sessions" value="24,861" delta="+12.4% this week" deltaTone="positive" />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Error rate" value="1.8%" delta="-0.4 pts" deltaTone="positive" />
        </BentoModule>
        <BentoModule cols={1} padding="none" interactive>
          <Link to="/quality" className="block h-full">
            <Kpi label="Data quality" value="94.8%" delta="Integrity" />
          </Link>
        </BentoModule>
        <BentoModule cols={3} rows={2} className="flex min-h-64 flex-col">
          <BentoTitle>Token consumption</BentoTitle>
          <Sparkline values={tokens} label="Token consumption trend" className="mt-8 h-32 flex-1" />
          <p className="mt-4 font-display text-kpi text-foreground">24.8M</p>
        </BentoModule>
        <BentoModule cols={1} rows={2}>
          <BentoTitle>Model mix</BentoTitle>
          <MixLegend items={models} className="mt-8" />
        </BentoModule>
        <BentoModule cols={2} rows={2}>
          <BentoTitle>Tool usage</BentoTitle>
          <BarList items={tools} className="mt-8" />
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi label="Avg session duration" value="4m 12s" delta="Median 3m 48s" />
        </BentoModule>
        <BentoModule cols={2}>
          <BentoTitle>Recent activity</BentoTitle>
          <ul className="mt-6 grid gap-4 text-secondary">
            <li className="flex justify-between gap-4 text-foreground-muted">
              <span>ses_8f21 · apply_patch</span>
              <span>2m ago</span>
            </li>
            <li className="flex justify-between gap-4 text-foreground-muted">
              <span>ses_12aa · tool error</span>
              <span>11m ago</span>
            </li>
            <li className="flex justify-between gap-4 text-foreground-muted">
              <span>ses_90c3 · completed</span>
              <span>18m ago</span>
            </li>
          </ul>
        </BentoModule>
      </BentoGrid>
    </div>
  )
}
