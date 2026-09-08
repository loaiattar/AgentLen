import type { LucideIcon } from 'lucide-react'
import { Link, type LinkProps } from '@tanstack/react-router'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'

import { Button } from '@/components/atoms/Button'
import { useUiStore } from '@/store/ui.store'
import { cn } from '@/lib/utils/cn'

export interface NavigationItem {
  label: string
  to: LinkProps['to']
  icon: LucideIcon
}

export interface NavigationProps {
  items: NavigationItem[]
}

export function Navigation({ items }: NavigationProps) {
  const isSidebarOpen = useUiStore((state) => state.isSidebarOpen)
  const toggleSidebar = useUiStore((state) => state.toggleSidebar)

  return (
    <nav
      className={cn(
        'flex h-full flex-col gap-1 border-r border-border bg-card p-2 transition-[width]',
        isSidebarOpen ? 'w-56' : 'w-14',
      )}
    >
      <Button
        variant="ghost"
        size="icon"
        className="mb-2 self-end"
        onClick={toggleSidebar}
        aria-label={isSidebarOpen ? 'Réduire la navigation' : 'Ouvrir la navigation'}
      >
        {isSidebarOpen ? <PanelLeftClose className="size-4" /> : <PanelLeftOpen className="size-4" />}
      </Button>

      {items.map((item) => {
        const Icon = item.icon
        return (
          <Link
            key={item.label}
            to={item.to}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground [&.active]:bg-accent [&.active]:text-accent-foreground"
            activeProps={{ className: 'active' }}
          >
            <Icon className="size-4 shrink-0" />
            {isSidebarOpen && <span>{item.label}</span>}
          </Link>
        )
      })}
    </nav>
  )
}
