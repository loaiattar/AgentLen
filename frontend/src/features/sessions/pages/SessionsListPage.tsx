import { Link } from '@tanstack/react-router'

import { Badge } from '@/components/ui/Badge'
import { BentoGrid, BentoModule } from '@/components/ui/Bento'
import { FilterBar, FilterChip } from '@/components/ui/FilterBar'
import { Kpi } from '@/components/ui/Kpi'
import { OverflowMenu } from '@/components/ui/OverflowMenu'
import { PageHeader } from '@/components/ui/PageHeader'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'

const sessions = [
  {
    id: 'ses_8f21',
    agent: 'codegen',
    model: 'gpt-4.1',
    duration: '6m 04s',
    tokens: '182k',
    tools: 24,
    errors: 0,
    timestamp: '14:22',
    status: 'ok' as const,
  },
  {
    id: 'ses_12aa',
    agent: 'reviewer',
    model: 'claude-sonnet',
    duration: '3m 11s',
    tokens: '94k',
    tools: 11,
    errors: 2,
    timestamp: '14:11',
    status: 'error' as const,
  },
  {
    id: 'ses_90c3',
    agent: 'planner',
    model: 'gpt-4.1',
    duration: '8m 40s',
    tokens: '241k',
    tools: 31,
    errors: 0,
    timestamp: '13:58',
    status: 'ok' as const,
  },
]

export function SessionsListPage() {
  return (
    <div>
      <PageHeader kicker="Sessions" title="Explorer" />
      <BentoGrid className="mb-8">
        <BentoModule cols={2} padding="none">
          <Kpi label="Total sessions" value="24,861" />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Active models" value="3" />
        </BentoModule>
        <BentoModule cols={1} padding="none">
          <Kpi label="Avg duration" value="4m 12s" />
        </BentoModule>
      </BentoGrid>
      <FilterBar>
        <FilterChip active>All sources</FilterChip>
        <FilterChip>Agent</FilterChip>
        <FilterChip>Model</FilterChip>
        <FilterChip>Period</FilterChip>
      </FilterBar>
      <div className="glass-surface rounded-xl p-2">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Session</TableHead>
              <TableHead>Agent</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Tokens</TableHead>
              <TableHead>Tools</TableHead>
              <TableHead>Errors</TableHead>
              <TableHead>Time</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sessions.map((session) => (
              <TableRow key={session.id}>
                <TableCell>
                  <Link to="/sessions/$sessionId" params={{ sessionId: session.id }} className="text-foreground">
                    {session.id}
                  </Link>
                </TableCell>
                <TableCell className="text-foreground-muted">{session.agent}</TableCell>
                <TableCell className="text-foreground-muted">{session.model}</TableCell>
                <TableCell>{session.duration}</TableCell>
                <TableCell>{session.tokens}</TableCell>
                <TableCell>{session.tools}</TableCell>
                <TableCell>{session.errors}</TableCell>
                <TableCell className="text-foreground-muted">{session.timestamp}</TableCell>
                <TableCell>
                  <Badge tone={session.status === 'ok' ? 'mint' : 'pink'}>{session.status}</Badge>
                </TableCell>
                <TableCell>
                  <OverflowMenu
                    items={[
                      { label: 'Open', onSelect: () => undefined },
                      { label: 'Export', onSelect: () => undefined },
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
