import { Outlet } from '@tanstack/react-router'
import { LayoutDashboard, Import, Sparkles, GitCompareArrows } from 'lucide-react'

import { Navigation, type NavigationItem } from '@/components/organisms/Navigation'

const navigationItems: NavigationItem[] = [
  { label: 'Dashboard', to: '/', icon: LayoutDashboard },
  { label: 'Imports', to: '/imports', icon: Import },
  { label: 'Assistant IA', to: '/import-assistant', icon: Sparkles },
  { label: 'Mappings', to: '/mappings', icon: GitCompareArrows },
]

export function AppLayout() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      <Navigation items={navigationItems} />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
