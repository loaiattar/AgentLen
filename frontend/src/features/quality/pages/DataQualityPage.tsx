import { BentoGrid, BentoModule, BentoTitle } from '@/components/ui/Bento'
import { Kpi } from '@/components/ui/Kpi'
import { PageHeader } from '@/components/ui/PageHeader'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'

const issues = [
  { id: 'dq_01', type: 'Missing fields', count: 128, note: 'tool_name absent on 1.1%' },
  { id: 'dq_02', type: 'Duplicates', count: 42, note: 'Same trace id, two imports' },
  { id: 'dq_03', type: 'Rejected records', count: 9, note: 'Unreadable JSONL lines' },
]

export function DataQualityPage() {
  return (
    <div>
      <PageHeader
        kicker="Data quality"
        title="Integrity"
        description="Imperfect data is acceptable when it is explained. Missing values stay missing."
      />
      <BentoGrid className="mb-8">
        <BentoModule cols={2} rows={2} className="flex min-h-56 flex-col justify-between">
          <BentoTitle>Data integrity</BentoTitle>
          <p className="font-display text-display text-foreground">94.8%</p>
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi label="Missing fields" value="128" />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Duplicates" value="42" />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Rejected" value="9" />
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi label="Schema consistency" value="98.1%" />
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi label="Mapping validity" value="96.4%" />
        </BentoModule>
      </BentoGrid>
      <div className="glass-surface rounded-xl p-2">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Issue</TableHead>
              <TableHead>Count</TableHead>
              <TableHead>Note</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {issues.map((issue) => (
              <TableRow key={issue.id}>
                <TableCell className="text-foreground">{issue.type}</TableCell>
                <TableCell>{issue.count}</TableCell>
                <TableCell className="text-foreground-muted">{issue.note}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
