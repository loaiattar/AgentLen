import { Link, useRouterState } from '@tanstack/react-router'

import { cn } from '@/lib/utils/cn'
import { StatusDot } from '@/components/ui/StatusDot'
import { isShellNavActive, SHELL_NAV_ITEMS, shellNavItemVariants } from '@/components/ui/shell-nav'

export function AppSidebar() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })

  return (
    <aside className="glass-surface hidden w-[var(--sidebar-width)] shrink-0 flex-col rounded-none border-y-0 border-l-0 lg:flex">
      <div className="flex h-[var(--header-height)] items-center px-[var(--space-3)]">
        <Link
          to="/"
          className="font-display text-section text-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary-emphasis focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          AgentScope
        </Link>
      </div>

      <nav aria-label="Main" className="flex flex-1 flex-col gap-[var(--space-1)] px-[var(--space-1)] py-[var(--space-2)]">
        {SHELL_NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const active = isShellNavActive(pathname, item.to)

          return (
            <Link
              key={item.to}
              to={item.to}
              aria-current={active ? 'page' : undefined}
              className={cn(shellNavItemVariants({ layout: 'sidebar', active }))}
            >
              {active ? (
                // tokens.md has no 2px width; w-0.5 is the closest hairline for the active cyan rail.
                <span className="absolute inset-y-[var(--space-1)] left-0 w-0.5 rounded-pill bg-primary-emphasis" />
              ) : null}
              <Icon className="size-4 shrink-0" aria-hidden />
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="grid gap-[var(--space-1)] border-t border-border px-[var(--space-3)] py-[var(--space-2)] text-secondary text-foreground-muted">
        <p className="flex items-center justify-between gap-[var(--space-1)]">
          <span>Provider</span>
          <span className="text-foreground">OpenAI</span>
        </p>
        <p className="flex items-center justify-between gap-[var(--space-1)]">
          <span>Model</span>
          <span className="text-foreground">gpt-4.1</span>
        </p>
        <p className="flex items-center gap-[var(--space-1)]">
          <StatusDot tone="live" label="System operational" />
          <span>Operational</span>
        </p>
        <p className="text-meta uppercase text-foreground-subtle">Workspace · HETIC</p>
      </div>
    </aside>
  )
}
