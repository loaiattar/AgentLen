import type { ReactNode } from 'react'

import { AppSidebar } from '@/components/ui/AppSidebar'
import { AtmosphericBackground } from '@/components/ui/AtmosphericBackground'
import { MobileNav } from '@/components/ui/MobileNav'
import { TopNav } from '@/components/ui/TopNav'

export interface ShellProps {
  children: ReactNode
}

export function Shell({ children }: ShellProps) {
  return (
    <div className="relative min-h-dvh bg-background">
      <AtmosphericBackground />
      <div className="flex min-h-dvh">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopNav />
          <main className="flex-1 px-[var(--space-2)] pb-[calc(var(--space-6)+var(--space-2))] md:px-[var(--space-4)] lg:pb-[var(--space-4)]">
            {children}
          </main>
        </div>
      </div>
      <MobileNav />
    </div>
  )
}
