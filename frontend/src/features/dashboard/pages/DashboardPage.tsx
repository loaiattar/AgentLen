import { Link } from '@tanstack/react-router'

import { AreaChart, BarList, MixLegend, Sparkline } from '@/components/ui/Chart'
import { BentoGrid, BentoModule, BentoTitle } from '@/components/ui/Bento'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Kpi } from '@/components/ui/Kpi'
import { PageHeader } from '@/components/ui/PageHeader'
import { GlassSkeleton } from '@/components/ui/Skeleton'
import {
  useDashboardActivityQuery,
  useDashboardModelsQuery,
  useDashboardOverviewQuery,
  useDashboardToolsQuery,
  useMetricDefinitionsQuery,
} from '@/features/dashboard/api/dashboard.queries'
import {
  aggregateModels,
  aggregateTools,
  coverageHint,
  formatCount,
  formatDurationMs,
  formatRatio,
  formatTokens,
  getDefinition,
  getMetric,
  knownTokensByDay,
  MISSING_VALUE,
  sessionsByDay,
} from '@/features/dashboard/lib/format'

function ChartEmpty({ message }: { message: string }) {
  return <p className="mt-8 text-body text-foreground-muted">{message}</p>
}

export function DashboardPage() {
  const overview = useDashboardOverviewQuery()
  const activity = useDashboardActivityQuery()
  const tools = useDashboardToolsQuery()
  const models = useDashboardModelsQuery()
  const definitions = useMetricDefinitionsQuery()

  const isPending = overview.isPending || activity.isPending || tools.isPending || models.isPending
  const isError = overview.isError || activity.isError || tools.isError || models.isError

  if (isPending) {
    return (
      <div>
        <PageHeader kicker="Overview" title="Agent activity" />
        <BentoGrid>
          {Array.from({ length: 6 }, (_, index) => (
            <BentoModule key={index} cols={index < 2 ? 2 : 1} padding="none">
              <GlassSkeleton />
            </BentoModule>
          ))}
        </BentoGrid>
      </div>
    )
  }

  if (isError) {
    const message =
      overview.error?.message ??
      activity.error?.message ??
      tools.error?.message ??
      models.error?.message ??
      'Unable to load metrics.'

    return (
      <div>
        <PageHeader kicker="Overview" title="Agent activity" />
        <EmptyState
          title="Metrics unavailable"
          description={message}
          action={
            <Button
              variant="secondary"
              onClick={() => {
                void overview.refetch()
                void activity.refetch()
                void tools.refetch()
                void models.refetch()
              }}
            >
              Retry
            </Button>
          }
        />
      </div>
    )
  }

  const metrics = overview.data?.metrics ?? []
  const definitionList = definitions.data?.definitions
  const sessionCount = getMetric(metrics, 'session_count')
  const errorRate = getMetric(metrics, 'tool_error_rate')
  const duration = getMetric(metrics, 'avg_session_duration_ms')
  const avgTokens = getMetric(metrics, 'avg_tokens_per_session')

  const activityPoints = activity.data?.points ?? []
  const sessionSeries = sessionsByDay(activityPoints)
  const tokenSeries = knownTokensByDay(activityPoints)
  const toolItems = aggregateTools(tools.data?.points ?? [])
  const modelItems = aggregateModels(models.data?.points ?? [])
  const modelWarnings = models.data?.warnings ?? []

  return (
    <div>
      <PageHeader kicker="Overview" title="Agent activity" description="A calm window into traces, tokens and failures." />
      <BentoGrid>
        <BentoModule cols={2} rows={2} className="flex min-h-72 flex-col justify-between xl:min-h-80">
          <BentoTitle>Agent activity</BentoTitle>
          {sessionSeries.length > 0 ? (
            <AreaChart values={sessionSeries} label="Sessions per day" className="mt-6 h-44" />
          ) : (
            <ChartEmpty message="No session activity for this period." />
          )}
        </BentoModule>

        <BentoModule cols={2} padding="none">
          <Kpi
            label="Total sessions"
            value={formatCount(sessionCount?.value)}
            hint={coverageHint(sessionCount)}
            title={getDefinition(definitionList, 'session_count')?.formula}
          />
        </BentoModule>

        <BentoModule cols={1} padding="none">
          <Kpi
            label="Error rate"
            value={formatRatio(errorRate?.value)}
            hint={coverageHint(errorRate)}
            title={getDefinition(definitionList, 'tool_error_rate')?.formula}
          />
        </BentoModule>

        <BentoModule cols={1} padding="none" interactive>
          <Link to="/quality" className="block h-full">
            <Kpi label="Data quality" value={MISSING_VALUE} delta="Integrity" />
          </Link>
        </BentoModule>

        <BentoModule cols={3} rows={2} className="flex min-h-64 flex-col">
          <BentoTitle>Token consumption</BentoTitle>
          {tokenSeries.length > 0 ? (
            <Sparkline values={tokenSeries} label="Known token volume per day" className="mt-8 h-32 flex-1" />
          ) : (
            <ChartEmpty message="No token data for this period." />
          )}
          <p
            className="mt-4 font-display text-kpi text-foreground"
            title={getDefinition(definitionList, 'avg_tokens_per_session')?.formula}
          >
            {formatTokens(avgTokens?.value)}
          </p>
          <p className="mt-1 text-secondary text-foreground-muted">
            {coverageHint(avgTokens) ?? 'Average tokens per session'}
          </p>
        </BentoModule>

        <BentoModule cols={1} rows={2}>
          <BentoTitle>Model mix</BentoTitle>
          {modelItems.length > 0 ? (
            <MixLegend items={modelItems} className="mt-8" />
          ) : (
            <ChartEmpty message="No model calls for this period." />
          )}
          {modelWarnings.map((warning) => (
            <p key={warning} className="mt-4 text-secondary text-foreground-subtle">
              {warning}
            </p>
          ))}
        </BentoModule>

        <BentoModule cols={2} rows={2}>
          <BentoTitle>Tool usage</BentoTitle>
          {toolItems.length > 0 ? (
            <BarList items={toolItems} className="mt-8" />
          ) : (
            <ChartEmpty message="No tool calls for this period." />
          )}
        </BentoModule>

        <BentoModule cols={2} padding="none">
          <Kpi
            label="Avg session duration"
            value={formatDurationMs(duration?.value)}
            hint={coverageHint(duration)}
            title={getDefinition(definitionList, 'avg_session_duration_ms')?.formula}
          />
        </BentoModule>

        <BentoModule cols={2}>
          <BentoTitle>Recent activity</BentoTitle>
          <p className="mt-6 text-body text-foreground-muted">
            Session details are not available until the exploration API is wired.
          </p>
        </BentoModule>
      </BentoGrid>
    </div>
  )
}
