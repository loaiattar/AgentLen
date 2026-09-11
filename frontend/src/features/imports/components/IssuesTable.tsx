import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Table, TableBody, TableCell, TableEmpty, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { cn } from '@/lib/utils/cn'
import { formatCount, severityTone } from '@/features/imports/lib/format'
import type { ImportIssue, ImportSeverity } from '@/features/imports/types'

const SEVERITIES: (ImportSeverity | 'all')[] = ['all', 'rejected', 'duplicate', 'warning']

export interface IssuesTableProps {
  issues: ImportIssue[]
  total?: number
  severity: ImportSeverity | 'all'
  onSeverityChange?: (severity: ImportSeverity | 'all') => void
  emptyMessage?: string
  /** Hides the severity filter — the preview's issue list is not paginated. */
  filterable?: boolean
}

/**
 * Rejections, duplicates and warnings, each with the line, the stable code and
 * the faulty field path. "An explained rejection" is a project-level
 * requirement (ARCHITECTURE §11) — never a bare count.
 */
export function IssuesTable({
  issues,
  total,
  severity,
  onSeverityChange,
  emptyMessage = 'No issue recorded.',
  filterable = true,
}: IssuesTableProps) {
  return (
    <div>
      {filterable && onSeverityChange ? (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          {SEVERITIES.map((option) => (
            <Button
              key={option}
              size="sm"
              variant={severity === option ? 'secondary' : 'ghost'}
              className={cn(severity === option && 'ring-1 ring-border-strong')}
              onClick={() => onSeverityChange(option)}
            >
              {option}
            </Button>
          ))}
          {total !== undefined ? (
            <span className="ml-auto text-secondary text-foreground-muted">
              {formatCount(total)} total
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="glass-surface overflow-x-auto rounded-xl p-2">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-20">Line</TableHead>
              <TableHead className="w-28">Severity</TableHead>
              <TableHead>Code</TableHead>
              <TableHead>Field</TableHead>
              <TableHead>Message</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {issues.length === 0 ? (
              <TableEmpty>{emptyMessage}</TableEmpty>
            ) : (
              issues.map((issue, index) => (
                <TableRow key={`${issue.code}-${issue.line_number ?? 'na'}-${index}`}>
                  <TableCell className="text-foreground-muted">
                    {issue.line_number ?? '—'}
                  </TableCell>
                  <TableCell>
                    <Badge tone={severityTone(issue.severity)}>{issue.severity}</Badge>
                  </TableCell>
                  <TableCell className="font-mono text-meta text-foreground">{issue.code}</TableCell>
                  <TableCell className="font-mono text-meta text-foreground-muted">
                    {issue.field_path ?? '—'}
                  </TableCell>
                  <TableCell className="text-foreground-muted">{issue.message}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
