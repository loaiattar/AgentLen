import { Badge } from '@/components/ui/Badge'
import { StatusDot } from '@/components/ui/StatusDot'
import { formatCount, formatDateTime, formatDuration, statusTone } from '@/features/imports/lib/format'
import { isTerminal, type ImportStatus } from '@/features/imports/types'

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'error' | 'warning' }) {
  return (
    <div className="glass-surface rounded-xl p-4">
      <p className="text-meta tracking-[0.14em] text-foreground-subtle uppercase">{label}</p>
      <p
        className={
          tone === 'error'
            ? 'mt-2 font-display text-card text-error'
            : tone === 'warning'
              ? 'mt-2 font-display text-card text-warning'
              : 'mt-2 font-display text-card text-foreground'
        }
      >
        {value}
      </p>
    </div>
  )
}

export interface ImportReportCardProps {
  run: ImportStatus
}

/**
 * Status + final report. While the run is not terminal the counters are the
 * worker's running totals, so they are labelled as in-flight rather than
 * presented as a bilan that is not one yet.
 */
export function ImportReportCard({ run }: ImportReportCardProps) {
  const tone = statusTone(run.status)
  const done = isTerminal(run.status)
  const { report } = run

  return (
    <div className="grid gap-6">
      <div className="glass-surface flex flex-wrap items-center justify-between gap-4 rounded-xl p-6">
        <div className="flex items-center gap-3">
          <StatusDot tone={tone.dot} label={run.status} />
          <div>
            <p className="text-card text-foreground">Import #{run.id}</p>
            <p className="mt-1 text-secondary text-foreground-muted">
              {run.file.original_name} · {run.data_source.slug} · {run.mapping.name} v
              {run.mapping.version}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge tone={tone.badge}>{run.status}</Badge>
          {!done ? (
            <span className="text-secondary text-foreground-muted">Polling every second…</span>
          ) : null}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Read" value={formatCount(report.records_read)} />
        <Stat label="Imported" value={formatCount(report.records_imported)} />
        <Stat
          label="Duplicates"
          value={formatCount(report.records_duplicate)}
          tone={report.records_duplicate > 0 ? 'warning' : undefined}
        />
        <Stat
          label="Rejected"
          value={formatCount(report.records_rejected)}
          tone={report.records_rejected > 0 ? 'error' : undefined}
        />
      </div>

      <dl className="grid grid-cols-2 gap-4 text-secondary md:grid-cols-3">
        <div>
          <dt className="text-foreground-subtle">Started</dt>
          <dd className="mt-1 text-foreground">{formatDateTime(run.started_at)}</dd>
        </div>
        <div>
          <dt className="text-foreground-subtle">Finished</dt>
          <dd className="mt-1 text-foreground">{formatDateTime(run.finished_at)}</dd>
        </div>
        <div>
          <dt className="text-foreground-subtle">Duration</dt>
          <dd className="mt-1 text-foreground">
            {formatDuration(run.started_at, run.finished_at)}
          </dd>
        </div>
      </dl>

      {report.fields_missing && Object.keys(report.fields_missing).length > 0 ? (
        <div>
          <h3 className="mb-3 text-card text-foreground">Fields missing from the source</h3>
          <p className="mb-4 max-w-2xl text-secondary text-foreground-muted">
            These targets had no value in the file. They are stored as null, never as zero — the
            dashboard reports them with a coverage ratio.
          </p>
          <ul className="glass-surface grid gap-2 rounded-xl p-4">
            {Object.entries(report.fields_missing).map(([field, count]) => (
              <li key={field} className="flex items-center justify-between gap-4 text-secondary">
                <span className="font-mono text-meta text-foreground">{field}</span>
                <span className="text-foreground-muted">{formatCount(count)} records</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
