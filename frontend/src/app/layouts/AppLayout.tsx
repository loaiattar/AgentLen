import { Outlet } from '@tanstack/react-router'

import { Shell } from '@/components/ui/Shell'

export function AppLayout() {
  return (
    <Shell>
      <Outlet />
    </Shell>
  )
}
