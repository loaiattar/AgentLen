import { useState } from 'react'
import { getRouteApi, Link } from '@tanstack/react-router'

import { Badge } from '@/components/ui/Badge'
import { BentoGrid, BentoModule } from '@/components/ui/Bento'
import { Button } from '@/components/ui/Button'
import { Drawer } from '@/components/ui/Drawer'
import { EmptyState } from '@/components/ui/EmptyState'
import { Kpi } from '@/components/ui/Kpi'
import { PageHeader } from '@/components/ui/PageHeader'
import { GlassSkeleton, Skeleton } from '@/components/ui/Skeleton'
import { Timeline, TimelineItem } from '@/components/ui/Timeline'
import type { TimelineItemProps } from '@/components/ui/Timeline'
import {
  useRawRecordQuery,
  useSessionQuery,
  useSessionTimelineQuery,
} from '@/features/sessions/api/sessions.queries'
import {
  formatCount,
  formatDurationMs,
  formatInstant,
  formatOutcome,
  outcomeTone,
} from '@/features/sessions/lib/format'
import type { ModelCallDetail, ToolCallDetail } from '@/features/sessions/types'
import { truncationNotice } from '@/lib/api/pagination'

const routeApi = getRouteApi('/_app/sessions/$sessionId')

function eventTitle(type: 'model_call' | 'tool_call', sequenceIndex: number): string {
  return type === 'model_call' ? `Model call · #${sequenceIndex}` : `Tool call · #${sequenceIndex}`
}

function eventTone(type: 'model_call' | 'tool_call', status: string): TimelineItemProps['tone'] {
  if (status === 'error') return 'error'
  return type === 'model_call' ? 'model' : 'tool'
}

function BackButton() {
  return (
    <Button variant="secondary" asChild>
      {/* Preserve the list's drill-down filters (#28) round-trip: they live in
          the shared /_app search state, carried into this route on the way in
          (openSession/useSessionIdSearch) — dropping them here would return to
          the unfiltered list. */}
      <Link to="/sessions" search={(prev) => prev}>
        Back
      </Link>
    </Button>
  )
}

function RawRecordDrawer({
  open,
  onOpenChange,
  query,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  query: ReturnType<typeof useRawRecordQuery>
}) {
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Raw record"
      description="The untouched source payload behind this event — nothing normalized or filtered."
    >
      {query.isPending ? (
        <Skeleton className="h-64" />
      ) : query.isError ? (
        <p className="text-body text-error">{query.error?.message ?? 'Unable to load this record.'}</p>
      ) : (
        <pre className="overflow-auto rounded-lg bg-surface-sunken p-4 text-meta text-foreground-muted">
          {JSON.stringify(query.data?.payload, null, 2)}
        </pre>
      )}
    </Drawer>
  )
}

export function SessionDetailPage() {
  const { sessionId } = routeApi.useParams()
  const id = Number(sessionId)
  const [openRawRecordId, setOpenRawRecordId] = useState<number | null>(null)

  const session = useSessionQuery(id)
  const timeline = useSessionTimelineQuery(id)
  const rawRecord = useRawRecordQuery(openRawRecordId ?? undefined)

  if (!Number.isInteger(id) || id <= 0) {
    return (
      <div>
        <PageHeader kicker="Session" title={sessionId} action={<BackButton />} />
        <EmptyState title="Invalid session id" description="This session id isn't a valid number." />
      </div>
    )
  }

  if (session.isPending || timeline.isPending) {
    return (
      <div>
        <PageHeader kicker="Session" title={sessionId} action={<BackButton />} />
        <BentoGrid>
          {Array.from({ length: 4 }, (_, index) => (
            <BentoModule key={index} cols={index < 2 ? 2 : 1} padding="none">
              <GlassSkeleton />
            </BentoModule>
          ))}
        </BentoGrid>
      </div>
    )
  }

  if (session.isError || timeline.isError) {
    return (
      <div>
        <PageHeader kicker="Session" title={sessionId} action={<BackButton />} />
        <EmptyState
          title="Session unavailable"
          description={
            session.error?.message ?? timeline.error?.message ?? 'Unable to load this session.'
          }
          action={
            <Button
              variant="secondary"
              onClick={() => {
                void session.refetch()
                void timeline.refetch()
              }}
            >
              Retry
            </Button>
          }
        />
      </div>
    )
  }

  const { session: info, model_calls: modelCalls, tool_calls: toolCalls } = session.data
  const events = timeline.data.items
  const timelineNotice = truncationNotice(timeline.data, 'events')
  // null isn't 0 (same rule as the dashboard): a call with no token counts at
  // all must not silently sum into a confident-looking 0. Only calls that
  // report *something* feed the total; "—" means truly nothing is known, not
  // "zero calls".
  const callsWithTokenData = modelCalls.filter(
    (call) => call.input_tokens != null || call.output_tokens != null,
  )
  const totalTokens = callsWithTokenData.reduce(
    (sum, call) => sum + (call.input_tokens ?? 0) + (call.output_tokens ?? 0),
    0,
  )

  return (
    <div>
      <PageHeader
        kicker="Session"
        title={info.external_id || String(info.id)}
        description={`Sourced from raw record #${info.raw_record_id}`}
        action={<BackButton />}
      />

      <BentoGrid className="mb-8">
        <BentoModule cols={1} padding="none">
          <Kpi label="Duration" value={formatDurationMs(info.duration_ms)} />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Tokens" value={callsWithTokenData.length === 0 ? '—' : formatCount(totalTokens)} />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Model calls" value={formatCount(modelCalls.length)} />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Tool calls" value={formatCount(toolCalls.length)} />
        </BentoModule>
        <BentoModule cols={2}>
          <p className="text-meta tracking-[0.14em] text-foreground-subtle uppercase">Agent / source</p>
          <p className="mt-4 font-display text-section text-foreground">
            {info.agent_id == null ? '—' : `Agent ${info.agent_id}`}
          </p>
          <p className="mt-1 text-secondary text-foreground-muted">Source {info.data_source_id}</p>
        </BentoModule>
        <BentoModule cols={2}>
          <p className="text-meta tracking-[0.14em] text-foreground-subtle uppercase">Status</p>
          <div className="mt-4">
            <Badge tone={outcomeTone(info.outcome)}>{formatOutcome(info.outcome)}</Badge>
          </div>
          <p className="mt-3 text-secondary text-foreground-muted">
            {formatInstant(info.started_at)} → {formatInstant(info.ended_at)}
          </p>
        </BentoModule>
      </BentoGrid>

      <section className="glass-surface rounded-xl p-6 md:p-8">
        <h2 className="mb-6 text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">
          Timeline
        </h2>
        {timelineNotice === null ? null : (
          <p role="status" className="mb-6 text-secondary text-warning">
            {timelineNotice}
          </p>
        )}
        {events.length === 0 ? (
          <p className="text-body text-foreground-muted">
            No model or tool calls recorded for this session.
          </p>
        ) : (
          <Timeline>
            {events.map(({ type, event }) => (
              <TimelineItem
                key={`${type}-${event.id}`}
                time={formatInstant(event.started_at)}
                tone={eventTone(type, event.status)}
                title={eventTitle(type, event.sequence_index)}
                detail={
                  <div className="flex flex-col items-start gap-2">
                    {type === 'model_call' ? (
                      <p>
                        {formatCount((event as ModelCallDetail).input_tokens)} in ·{' '}
                        {formatCount((event as ModelCallDetail).output_tokens)} out ·{' '}
                        {formatDurationMs(event.duration_ms)}
                      </p>
                    ) : (
                      <p>
                        {formatDurationMs(event.duration_ms)}
                        {(event as ToolCallDetail).error_message
                          ? ` · ${(event as ToolCallDetail).error_message}`
                          : ''}
                      </p>
                    )}
                    <Badge tone={event.status === 'error' ? 'pink' : 'neutral'}>{event.status}</Badge>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setOpenRawRecordId(event.raw_record_id)}
                    >
                      View raw record
                    </Button>
                  </div>
                }
              />
            ))}
          </Timeline>
        )}
      </section>

      <RawRecordDrawer
        open={openRawRecordId != null}
        onOpenChange={(open) => {
          if (!open) setOpenRawRecordId(null)
        }}
        query={rawRecord}
      />
    </div>
  )
}
