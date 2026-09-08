import { Outlet } from '@tanstack/react-router'

import { AppSidebar, MobileNav } from '@/components/ui/AppSidebar'
import { AtmosphericBackground } from '@/components/ui/AtmosphericBackground'
import { TopNav } from '@/components/ui/TopNav'

export function AppLayout() {
  return (
    <div className="relative min-h-dvh">
      <AtmosphericBackground />
      <div className="flex min-h-dvh">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopNav />
          <main className="flex-1 px-4 pb-24 md:px-8 lg:pb-10">
            <Outlet />
          </main>
        </div>
      </div>
      <MobileNav />
    </div>
  )
}
