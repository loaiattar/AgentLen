import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

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
  useDashboardQualityQuery,
  useDashboardToolsQuery,
  useMetricDefinitionsQuery,
} from '@/features/dashboard/api/dashboard.queries'
import {
  aggregateModels,
  aggregateTools,
  collectDashboardWarnings,
  coverageHint,
  dailySeries,
  type DayBucket,
  formatCount,
  formatDay,
  formatDurationMs,
  formatRatio,
  formatTokens,
  getDefinition,
  getMetric,
  hasKnownTokens,
  summarizeQuality,
} from '@/features/dashboard/lib/format'
import { toSessionSearch } from '@/features/dashboard/lib/filters'
import { useMetricsFilters } from '@/features/dashboard/hooks/useMetricsFilters'

function ChartEmpty({ message }: { message: string }) {
  return <p className="mt-8 text-body text-foreground-muted">{message}</p>
}

const drillDownClassName =
  'grid gap-1.5 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-primary-emphasis/70'

const dayColumnClassName =
  'block size-full rounded-sm outline-none transition-colors hover:bg-primary-soft/40 focus-visible:ring-2 focus-visible:ring-primary-emphasis/70'

const UNKNOWN_MODEL_HINT = '“unknown” counts calls with no model name. Sessions cannot be filtered on it, so it opens nothing.'

export function DashboardPage() {
  const { filters } = useMetricsFilters()
  const overview = useDashboardOverviewQuery(filters)
  const activity = useDashboardActivityQuery(filters)
  const tools = useDashboardToolsQuery(filters)
  const models = useDashboardModelsQuery(filters)
  const quality = useDashboardQualityQuery(filters)
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
  const days = dailySeries(activityPoints, filters)
  const dayLabels = days.map((bucket) => formatDay(bucket.day))
  // Without a source filter, the same tool or model name can come from several sources.
  const showSource = filters.data_source_id == null
  const toolItems = aggregateTools(tools.data?.points ?? [], { showSource })
  const modelItems = aggregateModels(models.data?.points ?? [], { showSource })

  const dayDrillDown = (describe: (bucket: DayBucket) => string) => (index: number, content: ReactNode) => {
    const bucket = days[index]
    const dayFilters = bucket?.filters
    if (!bucket || !dayFilters) return content
    const name = `${formatDay(bucket.day)}: ${describe(bucket)}`
    return (
      <Link to="/sessions" search={() => toSessionSearch(dayFilters)} aria-label={name} title={name} className={dayColumnClassName}>
        {content}
      </Link>
    )
  }
  const dashboardWarnings = collectDashboardWarnings(metrics, [activity.data, tools.data, models.data])

  return (
    <div>
      <PageHeader kicker="Overview" title="Agent activity" description="A calm window into traces, tokens and failures." />
      {dashboardWarnings.length > 0 ? (
        <ul
          role="status"
          className="mb-[var(--space-3)] grid gap-[var(--space-1)] rounded-xl bg-warning-soft px-[var(--space-2)] py-[var(--space-2)] text-body text-foreground"
        >
          {dashboardWarnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
      <BentoGrid>
        <BentoModule cols={2} rows={2} className="flex min-h-72 flex-col justify-between xl:min-h-80">
          <BentoTitle>Agent activity</BentoTitle>
          {days.length > 0 ? (
            <AreaChart
              values={days.map((bucket) => bucket.sessions)}
              xLabels={dayLabels}
              wrapColumn={dayDrillDown((bucket) => `${formatCount(bucket.sessions)} sessions`)}
              label="Sessions per day"
              className="mt-6 h-44"
            />
          ) : (
            <ChartEmpty message="No session activity for this period." />
          )}
        </BentoModule>

        <BentoModule cols={2} padding="none" interactive>
          <Link to="/sessions" search={(prev) => prev} className="block h-full">
            <Kpi
              label="Total sessions"
              value={formatCount(sessionCount?.value)}
              hint={coverageHint(sessionCount)}
              title={getDefinition(definitionList, 'session_count')?.formula}
            />
          </Link>
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
          <Link to="/quality" search={(prev) => prev} className="block h-full">
            <Kpi
              label="Data quality"
              value={formatRatio(summarizeQuality(quality.data?.points ?? []).rejectionRatio)}
              hint={quality.isError ? 'Unavailable' : 'Rejection rate'}
              title={getDefinition(definitionList, 'import_rejection_ratio')?.formula}
            />
          </Link>
        </BentoModule>

        <BentoModule cols={3} rows={2} className="flex min-h-64 flex-col">
          <BentoTitle>Token consumption</BentoTitle>
          {hasKnownTokens(activityPoints) ? (
            <Sparkline
              values={days.map((bucket) => bucket.tokens)}
              xLabels={dayLabels}
              wrapColumn={dayDrillDown((bucket) =>
                bucket.tokens == null ? 'tokens not reported' : `${formatTokens(bucket.tokens)} known tokens`,
              )}
              label="Known token volume per day"
              className="mt-8 h-32 flex-1"
            />
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
            <>
              <MixLegend
                items={modelItems}
                className="mt-8"
                wrapItem={(item, content) => {
                  const itemFilters = item.filters
                  if (!itemFilters) {
                    return (
                      <span className="flex w-full items-center justify-between gap-3" title={UNKNOWN_MODEL_HINT}>
                        {content}
                      </span>
                    )
                  }
                  return (
                    <Link
                      to="/sessions"
                      search={() => toSessionSearch(itemFilters)}
                      className="flex w-full items-center justify-between gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-primary-emphasis/70"
                    >
                      {content}
                    </Link>
                  )
                }}
              />
              {modelItems.some((item) => item.filters == null) ? (
                <p className="mt-4 text-meta text-foreground-subtle">{UNKNOWN_MODEL_HINT}</p>
              ) : null}
            </>
          ) : (
            <ChartEmpty message="No model calls for this period." />
          )}
        </BentoModule>

        <BentoModule cols={2} rows={2}>
          <BentoTitle>Tool usage</BentoTitle>
          {toolItems.length > 0 ? (
            <BarList
              items={toolItems}
              className="mt-8"
              wrapItem={(item, content) => (
                <Link to="/sessions" search={() => toSessionSearch(item.filters)} className={drillDownClassName}>
                  {content}
                </Link>
              )}
            />
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
          {activityPoints.length > 0 ? (
            <ul className="mt-6 grid gap-3">
              {[...activityPoints]
                .sort((left, right) => right.day.localeCompare(left.day))
                .slice(0, 5)
                .map((point) => (
                  <li key={`${point.day}-${point.data_source_id}`}>
                    <Link
                      to="/sessions"
                      search={() => toSessionSearch(point.filters)}
                      className="flex items-baseline justify-between gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-primary-emphasis/70"
                    >
                      <span className="text-secondary text-foreground-muted">{formatDay(point.day)}</span>
                      <span className="text-meta text-foreground">{formatCount(point.session_count)}</span>
                    </Link>
                  </li>
                ))}
            </ul>
          ) : (
            <p className="mt-6 text-body text-foreground-muted">No session activity for this period.</p>
          )}
        </BentoModule>
      </BentoGrid>
    </div>
  )
}
