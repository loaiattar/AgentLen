import { Link, useNavigate, useRouterState } from '@tanstack/react-router'
import { MoreHorizontal } from 'lucide-react'

import { cn } from '@/lib/utils/cn'
import { OverflowMenu } from '@/components/ui/OverflowMenu'
import {
  isShellNavActive,
  MOBILE_MORE_NAV,
  MOBILE_PRIMARY_NAV,
  shellNavItemVariants,
} from '@/components/ui/shell-nav'

export function MobileNav() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const navigate = useNavigate()
  const moreActive = MOBILE_MORE_NAV.some((item) => isShellNavActive(pathname, item.to))

  return (
    <nav
      aria-label="Main"
      className="glass-surface shadow-pop fixed inset-x-[var(--bento-gutter-mobile)] bottom-[var(--bento-gutter-mobile)] z-40 grid grid-cols-5 gap-[var(--space-1)] rounded-xl p-[var(--space-1)] lg:hidden"
    >
      {MOBILE_PRIMARY_NAV.map((item) => {
        const Icon = item.icon
        const active = isShellNavActive(pathname, item.to)

        return (
          <Link
            key={item.to}
            to={item.to}
            aria-label={item.label}
            aria-current={active ? 'page' : undefined}
            className={cn(shellNavItemVariants({ layout: 'mobile', active }))}
          >
            {active ? (
              // tokens.md has no 2px width; w-0.5 is the closest hairline for the active cyan rail.
              <span className="absolute inset-x-[var(--space-1)] top-0 h-0.5 rounded-pill bg-primary-emphasis" />
            ) : null}
            <Icon className="size-4" aria-hidden />
            <span className="max-w-full truncate">{item.label}</span>
          </Link>
        )
      })}

      <OverflowMenu
        label="More"
        side="top"
        items={MOBILE_MORE_NAV.map((item) => ({
          label: item.label,
          onSelect: () => {
            void navigate({ to: item.to })
          },
        }))}
        trigger={
          <button
            type="button"
            aria-label="More"
            className={cn(shellNavItemVariants({ layout: 'mobile', active: moreActive }), 'w-full')}
          >
            {moreActive ? (
              <span className="absolute inset-x-[var(--space-1)] top-0 h-0.5 rounded-pill bg-primary-emphasis" />
            ) : null}
            <MoreHorizontal className="size-4" aria-hidden />
            <span>More</span>
          </button>
        }
      />
    </nav>
  )
}
