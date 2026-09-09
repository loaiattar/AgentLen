import { BentoGrid, BentoModule, BentoTitle } from '@/components/ui/Bento'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Kpi } from '@/components/ui/Kpi'
import { PageHeader } from '@/components/ui/PageHeader'
import { GlassSkeleton } from '@/components/ui/Skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useDashboardQualityQuery, useMetricDefinitionsQuery } from '@/features/dashboard/api/dashboard.queries'
import {
  collectDashboardWarnings,
  formatCount,
  formatFieldsMissing,
  formatRatio,
  getDefinition,
  summarizeQuality,
} from '@/features/dashboard/lib/format'

export function DataQualityPage() {
  const quality = useDashboardQualityQuery()
  const definitions = useMetricDefinitionsQuery()

  if (quality.isPending) {
    return (
      <div>
        <PageHeader kicker="Data quality" title="Integrity" />
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

  if (quality.isError) {
    return (
      <div>
        <PageHeader kicker="Data quality" title="Integrity" />
        <EmptyState
          title="Quality metrics unavailable"
          description={quality.error?.message ?? 'Unable to load import quality.'}
          action={
            <Button variant="secondary" onClick={() => void quality.refetch()}>
              Retry
            </Button>
          }
        />
      </div>
    )
  }

  const points = quality.data?.points ?? []
  const summary = summarizeQuality(points)
  const warnings = collectDashboardWarnings([], [quality.data])
  const rejectionFormula = getDefinition(definitions.data?.definitions, 'import_rejection_ratio')?.formula

  if (points.length === 0) {
    return (
      <div>
        <PageHeader
          kicker="Data quality"
          title="Integrity"
          description="Imperfect data is acceptable when it is explained. Missing values stay missing."
        />
        {warnings.length > 0 ? (
          <ul
            role="status"
            className="mb-[var(--space-3)] grid gap-[var(--space-1)] rounded-xl bg-warning-soft px-[var(--space-2)] py-[var(--space-2)] text-body text-foreground"
          >
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        ) : null}
        <EmptyState
          title="No import quality yet"
          description="Quality metrics appear after an import run. Until then, missing values stay missing."
        />
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        kicker="Data quality"
        title="Integrity"
        description="Imperfect data is acceptable when it is explained. Missing values stay missing."
      />
      {warnings.length > 0 ? (
        <ul
          role="status"
          className="mb-[var(--space-3)] grid gap-[var(--space-1)] rounded-xl bg-warning-soft px-[var(--space-2)] py-[var(--space-2)] text-body text-foreground"
        >
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
      <BentoGrid className="mb-8">
        <BentoModule cols={2} rows={2} className="flex min-h-56 flex-col justify-between">
          <BentoTitle>Rejection rate</BentoTitle>
          <p className="font-display text-display text-foreground" title={rejectionFormula}>
            {formatRatio(summary.rejectionRatio)}
          </p>
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi label="Missing fields" value={formatCount(summary.fieldsMissing)} />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Duplicates" value={formatCount(summary.recordsDuplicate)} />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Rejected" value={formatCount(summary.recordsRejected)} />
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi label="Records read" value={formatCount(summary.recordsRead)} />
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi label="Records imported" value={formatCount(summary.recordsImported)} />
        </BentoModule>
      </BentoGrid>
      <div className="glass-surface rounded-xl p-2">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Import</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Read</TableHead>
              <TableHead>Imported</TableHead>
              <TableHead>Duplicates</TableHead>
              <TableHead>Rejected</TableHead>
              <TableHead>Rejection</TableHead>
              <TableHead>Issues</TableHead>
              <TableHead>Missing fields</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {points.map((point) => (
              <TableRow key={point.import_run_id}>
                <TableCell className="text-foreground">{point.import_run_id}</TableCell>
                <TableCell>{point.data_source_id}</TableCell>
                <TableCell className="text-foreground">{point.status}</TableCell>
                <TableCell>{formatCount(point.records_read)}</TableCell>
                <TableCell>{formatCount(point.records_imported)}</TableCell>
                <TableCell>{formatCount(point.records_duplicate)}</TableCell>
                <TableCell>{formatCount(point.records_rejected)}</TableCell>
                <TableCell>{formatRatio(point.rejection_ratio)}</TableCell>
                <TableCell>{formatCount(point.issue_count)}</TableCell>
                <TableCell className="text-foreground-muted">{formatFieldsMissing(point.fields_missing)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
