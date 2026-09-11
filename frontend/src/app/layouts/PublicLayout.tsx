import { Outlet } from '@tanstack/react-router'

import { AtmosphericBackground } from '@/components/ui/AtmosphericBackground'

export function PublicLayout() {
  return (
    <div className="relative min-h-dvh bg-background">
      <AtmosphericBackground />
      <Outlet />
    </div>
  )
}
