import { Badge } from '@/components/ui/Badge'
import { OverflowMenu } from '@/components/ui/OverflowMenu'
import { PageHeader } from '@/components/ui/PageHeader'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'

const mappings = [
  { name: 'TraceLab v3', source: 'TraceLab', version: '3.1', fields: 18, model: 'Configured model', status: 'active' },
  { name: 'SWE-chat core', source: 'SWE-chat', version: '1.4', fields: 12, model: 'Configured model', status: 'draft' },
]

export function MappingsListPage() {
  return (
    <div>
      <PageHeader kicker="Mappings" title="Library" />
      <div className="glass-surface rounded-xl p-2">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Fields</TableHead>
              <TableHead>AI model</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {mappings.map((mapping) => (
              <TableRow key={mapping.name}>
                <TableCell className="text-foreground">{mapping.name}</TableCell>
                <TableCell className="text-foreground-muted">{mapping.source}</TableCell>
                <TableCell>{mapping.version}</TableCell>
                <TableCell>{mapping.fields}</TableCell>
                <TableCell className="text-foreground-muted">{mapping.model}</TableCell>
                <TableCell>
                  <Badge tone={mapping.status === 'active' ? 'cyan' : 'neutral'}>{mapping.status}</Badge>
                </TableCell>
                <TableCell>
                  <OverflowMenu
                    items={[
                      { label: 'View' },
                      { label: 'Duplicate' },
                      { label: 'Archive', tone: 'danger' },
                    ]}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
