import { Link } from '@tanstack/react-router'
import { AlertTriangle } from 'lucide-react'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { formatBytes, formatCount } from '@/features/imports/lib/format'
import type { FileProfile, FileUpload } from '@/features/imports/types'

export interface FileSummaryProps {
  file: FileUpload
  profile: FileProfile | null
  acknowledged: boolean
  onAcknowledge: () => void
  onReplace: () => void
}

/**
 * File metadata plus the duplicate-import gate. Only `previous_import_run_ids`
 * proves a past import: `already_seen` just describes one upload and is false
 * on `GET /files/{id}`. Re-importing is legitimate — a fixed mapping, a re-run
 * after rejections — so this warns and asks, it does not block.
 */
export function FileSummary({
  file,
  profile,
  acknowledged,
  onAcknowledge,
  onReplace,
}: FileSummaryProps) {
  const alreadyImported = file.previous_import_run_ids.length > 0

  return (
    <div className="glass-surface rounded-xl p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate text-card text-foreground" title={file.original_name}>
            {file.original_name}
          </p>
          <p className="mt-1 font-mono text-meta text-foreground-subtle">
            {file.content_hash.slice(0, 16)}…
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="cyan">{file.format}</Badge>
          <Button variant="ghost" size="sm" onClick={onReplace}>
            Replace
          </Button>
        </div>
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-4 text-secondary md:grid-cols-4">
        <div>
          <dt className="text-foreground-subtle">Size</dt>
          <dd className="mt-1 text-foreground">{formatBytes(file.size_bytes)}</dd>
        </div>
        <div>
          <dt className="text-foreground-subtle">Records</dt>
          <dd className="mt-1 text-foreground">{formatCount(profile?.record_count)}</dd>
        </div>
        <div>
          <dt className="text-foreground-subtle">Sampled</dt>
          <dd className="mt-1 text-foreground">{formatCount(profile?.sampled_records)}</dd>
        </div>
        <div>
          <dt className="text-foreground-subtle">Fields</dt>
          <dd className="mt-1 text-foreground">{formatCount(profile?.fields.length)}</dd>
        </div>
      </dl>

      {alreadyImported ? (
        <div className="mt-6 rounded-lg bg-warning-soft p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
            <div className="min-w-0">
              <p className="text-body text-foreground">This file has already been imported.</p>
              <p className="mt-1 text-secondary text-foreground-muted">
                Identical content was imported by run
                {file.previous_import_run_ids.length > 1 ? 's' : ''}{' '}
                {file.previous_import_run_ids.map((runId, index) => (
                  <span key={runId}>
                    {index > 0 ? ', ' : ''}
                    <Link
                      to="/imports/$importId"
                      params={{ importId: String(runId) }}
                      className="text-primary underline-offset-4 hover:underline"
                    >
                      #{runId}
                    </Link>
                  </span>
                ))}
                . Re-importing is safe — records already present are counted as duplicates, not
                inserted twice — but confirm this is what you want.
              </p>
              {acknowledged ? (
                <p className="mt-3 text-secondary text-foreground-muted">Acknowledged.</p>
              ) : (
                <Button variant="secondary" size="sm" className="mt-3" onClick={onAcknowledge}>
                  Import it anyway
                </Button>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
