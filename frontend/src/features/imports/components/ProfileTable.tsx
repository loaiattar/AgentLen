import { Badge } from '@/components/ui/Badge'
import { Table, TableBody, TableCell, TableEmpty, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { formatCount, formatRatio, truncate } from '@/features/imports/lib/format'
import type { FileProfile } from '@/features/imports/types'

export interface ProfileTableProps {
  profile: FileProfile
}

/**
 * The field profile as the backend computed it (#48): JSONPath-addressed
 * leaves, types, null and distinct ratios, examples. This is what the user
 * reads before deciding a mapping is the right one.
 */
export function ProfileTable({ profile }: ProfileTableProps) {
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-baseline gap-x-6 gap-y-1 text-secondary text-foreground-muted">
        <span>
          <span className="text-foreground">{formatCount(profile.record_count)}</span> records
        </span>
        <span>
          <span className="text-foreground">{formatCount(profile.sampled_records)}</span> sampled
        </span>
        <span>
          <span className="text-foreground">{formatCount(profile.fields.length)}</span> fields
        </span>
      </div>

      <div className="glass-surface overflow-x-auto rounded-xl p-2">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Field</TableHead>
              <TableHead>Types</TableHead>
              <TableHead className="text-right">Null</TableHead>
              <TableHead className="text-right">Distinct</TableHead>
              <TableHead>Examples</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {profile.fields.length === 0 ? (
              <TableEmpty>No field could be read from this file.</TableEmpty>
            ) : (
              profile.fields.map((field) => (
                <TableRow key={field.path}>
                  <TableCell className="font-mono text-secondary text-foreground">
                    {field.path}
                  </TableCell>
                  <TableCell>
                    <span className="flex flex-wrap gap-1">
                      {field.types.map((type) => (
                        <Badge key={type} tone={type === 'null' ? 'neutral' : 'cyan'}>
                          {type}
                        </Badge>
                      ))}
                    </span>
                  </TableCell>
                  <TableCell className="text-right text-foreground-muted">
                    {formatRatio(field.null_ratio)}
                  </TableCell>
                  <TableCell className="text-right text-foreground-muted">
                    {formatRatio(field.distinct_ratio)}
                  </TableCell>
                  <TableCell className="text-foreground-muted">
                    <span className="font-mono text-meta">
                      {field.examples.length > 0
                        ? truncate(field.examples.slice(0, 2).join(' · '), 56)
                        : '—'}
                    </span>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
