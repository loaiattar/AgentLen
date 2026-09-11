import { AreaChart, BarList, MixLegend, Sparkline } from '@/components/ui/Chart'
import { BentoGrid, BentoModule, BentoTitle } from '@/components/ui/Bento'
import { Kpi } from '@/components/ui/Kpi'

const SESSION_SERIES = [12, 18, 15, 24, 22, 31, 28, 36, 33, 42]
const TOKEN_SERIES = [38, 44, 41, 55, 52, 64, 61, 73, 70, 82]

export function DashboardPreview() {
  return (
    <div className="atmosphere relative h-full min-h-80 overflow-hidden p-[var(--space-2)] md:min-h-[28rem] md:p-[var(--space-3)]">
      <BentoGrid className="pointer-events-none">
        <BentoModule cols={2} rows={2} className="flex min-h-52 flex-col justify-between xl:min-h-64">
          <BentoTitle>Agent activity</BentoTitle>
          <AreaChart values={SESSION_SERIES} label="Sessions per day" className="mt-6 h-32" />
        </BentoModule>

        <BentoModule cols={2} padding="none">
          <Kpi label="Total sessions" value="24,861" delta="+12.4%" deltaTone="positive" />
        </BentoModule>

        <BentoModule cols={1} padding="none">
          <Kpi label="Error rate" value="1.8%" hint="Tool failures" />
        </BentoModule>

        <BentoModule cols={1} padding="none">
          <Kpi label="Data quality" value="1.2%" hint="Rejection rate" />
        </BentoModule>

        <BentoModule cols={3} rows={2} className="hidden flex-col md:flex">
          <BentoTitle>Token consumption</BentoTitle>
          <Sparkline values={TOKEN_SERIES} label="Known token volume per day" className="mt-8 h-24 flex-1" />
          <p className="mt-4 font-display text-kpi text-foreground">184k</p>
          <p className="mt-1 text-secondary text-foreground-muted">Average tokens per session</p>
        </BentoModule>

        <BentoModule cols={1} rows={2} className="hidden md:block">
          <BentoTitle>Model mix</BentoTitle>
          <MixLegend
            className="mt-8"
            items={[
              { label: 'Claude', value: 48, tone: 'magenta' },
              { label: 'GPT', value: 32, tone: 'cyan' },
              { label: 'Codex', value: 20, tone: 'blue' },
            ]}
          />
        </BentoModule>

        <BentoModule cols={2} rows={2} className="hidden xl:block">
          <BentoTitle>Tool usage</BentoTitle>
          <BarList
            className="mt-8"
            items={[
              { label: 'Bash', value: 3820, tone: 'cyan' },
              { label: 'Read', value: 2910, tone: 'blue' },
              { label: 'Edit', value: 1240, tone: 'magenta' },
            ]}
          />
        </BentoModule>
      </BentoGrid>
    </div>
  )
}
