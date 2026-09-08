import { Link, useRouterState } from '@tanstack/react-router'
import {
  Activity,
  Database,
  FolderInput,
  GitBranch,
  LayoutGrid,
  ShieldCheck,
} from 'lucide-react'

import { cn } from '@/lib/utils/cn'
import { StatusDot } from '@/components/ui/StatusDot'

const navItems = [
  { to: '/', label: 'Overview', icon: LayoutGrid },
  { to: '/sessions', label: 'Sessions', icon: Activity },
  { to: '/imports', label: 'Imports', icon: FolderInput },
  { to: '/sources', label: 'Data Sources', icon: Database },
  { to: '/mappings', label: 'Mappings', icon: GitBranch },
  { to: '/quality', label: 'Data Quality', icon: ShieldCheck },
] as const

export function AppSidebar() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })

  return (
    <aside className="glass-surface hidden w-[var(--sidebar-width)] shrink-0 flex-col rounded-none border-y-0 border-l-0 lg:flex">
      <div className="flex h-[var(--header-height)] items-center px-6">
        <Link to="/" className="font-display text-section text-foreground">
          AgentScope
        </Link>
      </div>
      <nav className="flex flex-1 flex-col gap-1 px-3 py-4">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = item.to === '/' ? pathname === '/' : pathname.startsWith(item.to)

          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                'relative flex items-center gap-3 rounded-md px-3 py-2 text-body text-foreground-muted transition-colors',
                'hover:bg-primary-soft hover:text-foreground',
                active && 'bg-primary-soft text-foreground',
              )}
            >
              {active ? <span className="absolute inset-y-2 left-0 w-0.5 rounded-pill bg-primary-emphasis" /> : null}
              <Icon className="size-4" />
              {item.label}
            </Link>
          )
        })}
      </nav>
      <div className="grid gap-3 px-6 py-5 text-secondary text-foreground-muted">
        <p className="flex items-center justify-between">
          <span>Provider</span>
          <span className="text-foreground">OpenAI</span>
        </p>
        <p className="flex items-center justify-between">
          <span>Model</span>
          <span className="text-foreground">gpt-4.1</span>
        </p>
        <p className="flex items-center gap-2">
          <StatusDot tone="live" label="System operational" />
          <span>Operational</span>
        </p>
        <p className="text-meta tracking-[0.12em] uppercase">Workspace · HETIC</p>
      </div>
    </aside>
  )
}

export function MobileNav() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })

  return (
    <nav className="glass-surface fixed inset-x-3 bottom-3 z-40 grid grid-cols-6 gap-1 rounded-xl p-1 lg:hidden">
      {navItems.map((item) => {
        const Icon = item.icon
        const active = item.to === '/' ? pathname === '/' : pathname.startsWith(item.to)

        return (
          <Link
            key={item.to}
            to={item.to}
            aria-label={item.label}
            className={cn(
              'flex flex-col items-center justify-center rounded-md py-2 text-foreground-subtle',
              active && 'bg-primary-soft text-foreground',
            )}
          >
            <Icon className="size-4" />
          </Link>
        )
      })}
    </nav>
  )
}
