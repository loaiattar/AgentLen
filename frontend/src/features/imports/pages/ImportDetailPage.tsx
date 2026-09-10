import { useState } from 'react'
import { getRouteApi, Link } from '@tanstack/react-router'

import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { PageHeader } from '@/components/ui/PageHeader'
import { GlassSkeleton } from '@/components/ui/Skeleton'
import { ImportReportCard } from '@/features/imports/components/ImportReportCard'
import { IssuesTable } from '@/features/imports/components/IssuesTable'
import { useImportIssuesQuery, useImportQuery } from '@/features/imports/api/imports.queries'
import { formatCount } from '@/features/imports/lib/format'
import type { ImportSeverity } from '@/features/imports/types'

const routeApi = getRouteApi('/_app/imports/$importId')
const PAGE_SIZE = 25

export function ImportDetailPage() {
  const { importId } = routeApi.useParams()
  const [severity, setSeverity] = useState<ImportSeverity | 'all'>('all')
  const [offset, setOffset] = useState(0)

  const parsedId = Number(importId)
  const runId = Number.isFinite(parsedId) ? parsedId : null

  // Keeps polling while the run is still moving, then stops by itself.
  const run = useImportQuery(runId)
  const issues = useImportIssuesQuery(runId, severity === 'all' ? undefined : severity, {
    limit: PAGE_SIZE,
    offset,
  })

  const back = (
    <Button variant="secondary" asChild>
      <Link to="/imports">Back to history</Link>
    </Button>
  )

  if (runId === null) {
    return (
      <div>
        <PageHeader kicker="Import" title={importId} action={back} />
        <EmptyState title="Unknown import" description={`"${importId}" is not a run id.`} />
      </div>
    )
  }

  if (run.isPending) {
    return (
      <div>
        <PageHeader kicker="Import" title={`#${importId}`} action={back} />
        <GlassSkeleton className="h-64" />
      </div>
    )
  }

  if (run.isError) {
    return (
      <div>
        <PageHeader kicker="Import" title={`#${importId}`} action={back} />
        <EmptyState
          title="This import could not be loaded"
          description={run.error.message}
          action={
            <Button variant="secondary" onClick={() => void run.refetch()}>
              Retry
            </Button>
          }
        />
      </div>
    )
  }

  const total = issues.data?.total ?? 0

  return (
    <div>
      <PageHeader
        kicker="Import"
        title={`#${run.data.id} · ${run.data.file.original_name}`}
        action={back}
      />

      <ImportReportCard run={run.data} />

      <section className="mt-10">
        <h2 className="font-display text-section text-foreground">Issues</h2>
        <p className="mt-1 max-w-2xl text-body text-foreground-muted">
          Every rejected, duplicated or flagged record, with the line it came from and why it was
          not imported.
        </p>

        <div className="mt-6">
          {issues.isPending ? (
            <GlassSkeleton className="h-48" />
          ) : issues.isError ? (
            <p role="alert" className="text-secondary text-error">
              {issues.error.message}
            </p>
          ) : (
            <>
              <IssuesTable
                issues={issues.data.items}
                total={total}
                severity={severity}
                onSeverityChange={(next) => {
                  setSeverity(next)
                  setOffset(0)
                }}
                emptyMessage={
                  severity === 'all'
                    ? 'No issue recorded for this run.'
                    : `No ${severity} issue for this run.`
                }
              />

              {total > PAGE_SIZE ? (
                <div className="mt-4 flex items-center justify-between gap-4">
                  <p className="text-secondary text-foreground-muted">
                    {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {formatCount(total)}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={offset === 0}
                      onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={offset + PAGE_SIZE >= total}
                      onClick={() => setOffset((current) => current + PAGE_SIZE)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </section>
    </div>
  )
}
