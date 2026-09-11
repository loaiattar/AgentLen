import { Badge } from '@/components/ui/Badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { IssuesTable } from '@/features/imports/components/IssuesTable'
import { formatCount, formatExample, totalCount } from '@/features/imports/lib/format'
import type { ImportPreview, PreviewEntities } from '@/features/imports/types'

const PREVIEW_ROW_LIMIT = 10

/**
 * Columns are taken from the rows themselves — a preview row is untyped by
 * design — but only from the rows actually rendered. Unioning every row's keys
 * gave a header to a column that first appears on row 40, followed by eleven
 * empty cells: that reads as "the mapping produced nothing for this target"
 * rather than "this column is below the cut".
 */
function columnsOf(rows: PreviewEntities['rows']): string[] {
  const seen = new Set<string>()
  for (const row of rows) {
    for (const key of Object.keys(row)) seen.add(key)
  }
  return [...seen]
}

function EntityPreview({ entity }: { entity: PreviewEntities }) {
  const rows = entity.rows.slice(0, PREVIEW_ROW_LIMIT)
  const columns = columnsOf(rows)

  return (
    <div>
      <div className="mb-3 flex items-baseline gap-3">
        <h3 className="text-card text-foreground">{entity.target}</h3>
        <span className="text-secondary text-foreground-muted">
          {formatCount(entity.rows.length)} rows shown
        </span>
      </div>
      <div className="glass-surface overflow-x-auto rounded-xl p-2">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((column) => (
                <TableHead key={column} className="font-mono text-meta whitespace-nowrap">
                  {column}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, index) => (
              <TableRow key={index}>
                {columns.map((column) => (
                  <TableCell
                    key={column}
                    className="font-mono text-meta whitespace-nowrap text-foreground-muted"
                  >
                    {formatExample(row[column])}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

export interface PreviewPanelProps {
  preview: ImportPreview
}

/**
 * The dry-run result: what *would* be written and what *would* be rejected.
 * Nothing here has touched the database — this is the gate the user validates
 * before the real import.
 */
export function PreviewPanel({ preview }: PreviewPanelProps) {
  const imported = totalCount(preview.would_import)

  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone="neutral">{formatCount(preview.sampled)} sampled</Badge>
        <Badge tone="mint">{formatCount(imported)} would import</Badge>
        <Badge tone={preview.would_reject > 0 ? 'pink' : 'neutral'}>
          {formatCount(preview.would_reject)} would reject
        </Badge>
        <span className="text-secondary text-foreground-subtle">Nothing has been written.</span>
      </div>

      <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Object.entries(preview.would_import).map(([target, count]) => (
          <div key={target} className="glass-surface rounded-xl p-4">
            <dt className="text-meta tracking-[0.14em] text-foreground-subtle uppercase">
              {target}
            </dt>
            <dd className="mt-2 font-display text-card text-foreground">{formatCount(count)}</dd>
          </div>
        ))}
      </dl>

      {preview.entities.map((entity) => (
        <EntityPreview key={entity.target} entity={entity} />
      ))}

      <div>
        <h3 className="mb-3 text-card text-foreground">
          Issues on the sample
          {preview.issues.length > 0 ? (
            <span className="ml-2 text-secondary text-foreground-muted">
              {formatCount(preview.issues.length)}
            </span>
          ) : null}
        </h3>
        <IssuesTable
          issues={preview.issues}
          severity="all"
          filterable={false}
          emptyMessage="No record was rejected on this sample."
        />
      </div>
    </div>
  )
}
