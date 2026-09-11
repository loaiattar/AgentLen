import { Link, useRouterState } from '@tanstack/react-router'

import { cn } from '@/lib/utils/cn'
import { StatusDot, type StatusDotProps } from '@/components/ui/StatusDot'
import { Wordmark } from '@/components/ui/Wordmark'
import { isShellNavActive, SHELL_NAV_ITEMS, shellNavItemVariants } from '@/components/ui/shell-nav'

export interface AppSidebarDetail {
  label: string
  value: string
  /** The value is a placeholder (loading, unavailable, missing), not data. */
  muted?: boolean
}

export interface AppSidebarStatus {
  tone: NonNullable<StatusDotProps['tone']>
  label: string
}

export interface AppSidebarProps {
  details?: AppSidebarDetail[]
  status?: AppSidebarStatus
}

export function AppSidebar({ details = [], status }: AppSidebarProps) {
  const pathname = useRouterState({ select: (state) => state.location.pathname })

  return (
    <aside className="glass-surface hidden w-[var(--sidebar-width)] shrink-0 flex-col rounded-none border-y-0 border-l-0 lg:flex">
      <div className="flex h-[var(--header-height)] items-center px-[var(--space-3)]">
        <Link
          to="/overview"
          search={(prev) => prev}
          className="outline-none focus-visible:ring-2 focus-visible:ring-primary-emphasis focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          <Wordmark />
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
              search={(prev) => prev}
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

      {details.length > 0 || status ? (
        <div className="grid gap-[var(--space-1)] border-t border-border px-[var(--space-3)] py-[var(--space-2)] text-secondary text-foreground-muted">
          {details.map((detail) => (
            <p key={detail.label} className="flex items-center justify-between gap-[var(--space-1)]">
              <span className="shrink-0">{detail.label}</span>
              <span
                title={detail.value}
                className={cn('min-w-0 truncate', detail.muted ? 'text-foreground-subtle' : 'text-foreground')}
              >
                {detail.value}
              </span>
            </p>
          ))}
          {status ? (
            <p role="status" className="flex items-center gap-[var(--space-1)]">
              <StatusDot tone={status.tone} label={status.label} aria-hidden />
              <span>{status.label}</span>
            </p>
          ) : null}
        </div>
      ) : null}
    </aside>
  )
}
