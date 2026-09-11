import { Link } from '@tanstack/react-router'

import { Badge } from '@/components/ui/Badge'
import { BentoGrid, BentoModule, BentoTitle } from '@/components/ui/Bento'
import { buttonVariants } from '@/components/ui/Button'
import { Kpi } from '@/components/ui/Kpi'
import { OverflowMenu } from '@/components/ui/OverflowMenu'
import { PageHeader } from '@/components/ui/PageHeader'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'

const imports = [
  { id: 'imp_01', filename: 'tracelab.jsonl', source: 'TraceLab', date: '08 Sep', records: '12,440', status: 'completed' },
  { id: 'imp_02', filename: 'swe-chat.csv', source: 'SWE-chat', date: '07 Sep', records: '8,102', status: 'completed' },
  { id: 'imp_03', filename: 'unknown.parquet', source: 'Unknown', date: '06 Sep', records: '—', status: 'review' },
]

export function ImportListPage() {
  return (
    <div>
      <PageHeader kicker="Imports" title="Datasets" />
      <BentoGrid className="mb-8">
        <BentoModule cols={2} rows={2} className="flex min-h-56 flex-col justify-between">
          <div>
            <BentoTitle>New import</BentoTitle>
            <p className="mt-4 max-w-sm text-body text-foreground-muted">JSONL, CSV or Parquet. The assistant proposes a mapping. You validate.</p>
          </div>
          <Link to="/import-assistant" search={(prev) => prev} className={buttonVariants()}>
            Start import
          </Link>
        </BentoModule>
        <BentoModule cols={2} padding="none">
          <Kpi label="Completed" value="18" />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Duplicates" value="42" />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Rejected" value="9" />
        </BentoModule>
      </BentoGrid>
      <div className="glass-surface rounded-xl p-2">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>File</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Records</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {imports.map((item) => (
              <TableRow key={item.id}>
                <TableCell>
                  <Link
                    to="/imports/$importId"
                    params={{ importId: item.id }}
                    search={(prev) => prev}
                    className="text-foreground"
                  >
                    {item.filename}
                  </Link>
                </TableCell>
                <TableCell className="text-foreground-muted">{item.source}</TableCell>
                <TableCell className="text-foreground-muted">{item.date}</TableCell>
                <TableCell>{item.records}</TableCell>
                <TableCell>
                  <Badge tone={item.status === 'completed' ? 'mint' : 'magenta'}>{item.status}</Badge>
                </TableCell>
                <TableCell>
                  <OverflowMenu items={[{ label: 'Open' }, { label: 'Retry', disabled: item.status === 'completed' }]} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
