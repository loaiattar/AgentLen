import { useState } from 'react'
import { Link } from '@tanstack/react-router'

import { Badge } from '@/components/ui/Badge'
import { BentoGrid, BentoModule, BentoTitle } from '@/components/ui/Bento'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Kpi } from '@/components/ui/Kpi'
import { PageHeader } from '@/components/ui/PageHeader'
import { GlassSkeleton } from '@/components/ui/Skeleton'
import { StatusDot } from '@/components/ui/StatusDot'
import { Table, TableBody, TableCell, TableEmpty, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useImportsQuery } from '@/features/imports/api/imports.queries'
import { formatCount, formatDateTime, statusTone } from '@/features/imports/lib/format'
import type { ImportStatus } from '@/features/imports/types'

const PAGE_SIZE = 20

/** Counted over the page in view, not the whole history — the API returns no such aggregate. */
function summarize(items: ImportStatus[]) {
  return {
    imported: items.reduce((sum, run) => sum + run.report.records_imported, 0),
    duplicate: items.reduce((sum, run) => sum + run.report.records_duplicate, 0),
    rejected: items.reduce((sum, run) => sum + run.report.records_rejected, 0),
  }
}

export function ImportListPage() {
  const [offset, setOffset] = useState(0)
  const imports = useImportsQuery({ limit: PAGE_SIZE, offset })

  const items = imports.data?.items ?? []
  const total = imports.data?.total ?? 0
  const totals = summarize(items)

  const startImport = (
    <Button asChild>
      <Link to="/imports/new" search={(prev) => prev}>
        Start import
      </Link>
    </Button>
  )

  if (imports.isError) {
    return (
      <div>
        <PageHeader title="Imports" action={startImport} />
        <EmptyState
          title="The import history is unavailable"
          description={imports.error.message}
          action={
            <Button variant="secondary" onClick={() => void imports.refetch()}>
              Retry
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div>
      <PageHeader title="Imports" action={startImport} />

      <BentoGrid className="mb-8">
        <BentoModule cols={2} rows={2} className="flex min-h-56 flex-col justify-between">
          <div>
            <BentoTitle>New import</BentoTitle>
            <p className="mt-4 max-w-sm text-body text-foreground-muted">
              JSONL, CSV or Parquet. Profile the file, preview what the mapping would produce, then
              import.
            </p>
          </div>
          {startImport}
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi
            label="Runs"
            value={imports.isPending ? '—' : formatCount(total)}
            hint="Across the whole history"
          />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi
            label="Imported"
            value={imports.isPending ? '—' : formatCount(totals.imported)}
            hint="This page"
          />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi
            label="Rejected"
            value={imports.isPending ? '—' : formatCount(totals.rejected)}
            hint="This page"
          />
        </BentoModule>
      </BentoGrid>

      {imports.isPending ? (
        <GlassSkeleton className="h-64" />
      ) : total === 0 ? (
        <EmptyState
          title="No import yet"
          description="Upload a trace file to run the first import. The assistant profiles it, you validate the preview, the worker does the rest."
          action={startImport}
        />
      ) : (
        <>
          <div className="glass-surface overflow-x-auto rounded-xl p-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>File</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Mapping</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead className="text-right">Imported</TableHead>
                  <TableHead className="text-right">Duplicates</TableHead>
                  <TableHead className="text-right">Rejected</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.length === 0 ? (
                  <TableEmpty>No import on this page.</TableEmpty>
                ) : (
                  items.map((run) => {
                    const tone = statusTone(run.status)
                    return (
                      <TableRow key={run.id}>
                        <TableCell>
                          <Link
                            to="/imports/$importId"
                            params={{ importId: String(run.id) }}
                            className="text-foreground underline-offset-4 hover:underline"
                          >
                            {run.file.original_name}
                          </Link>
                        </TableCell>
                        <TableCell className="text-foreground-muted">
                          {run.data_source.slug}
                        </TableCell>
                        <TableCell className="text-foreground-muted">
                          {run.mapping.name} v{run.mapping.version}
                        </TableCell>
                        <TableCell className="text-foreground-muted">
                          {formatDateTime(run.started_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          {formatCount(run.report.records_imported)}
                        </TableCell>
                        <TableCell className="text-right text-foreground-muted">
                          {formatCount(run.report.records_duplicate)}
                        </TableCell>
                        <TableCell className="text-right text-foreground-muted">
                          {formatCount(run.report.records_rejected)}
                        </TableCell>
                        <TableCell>
                          <span className="inline-flex items-center gap-2">
                            <StatusDot tone={tone.dot} label={run.status} />
                            <Badge tone={tone.badge}>{run.status}</Badge>
                          </span>
                        </TableCell>
                      </TableRow>
                    )
                  })
                )}
              </TableBody>
            </Table>
          </div>

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
  )
}
