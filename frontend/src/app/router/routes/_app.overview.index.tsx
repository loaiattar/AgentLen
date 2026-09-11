import { createFileRoute, lazyRouteComponent } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/overview/')({
  component: lazyRouteComponent(() => import('@/features/dashboard/pages/DashboardPage'), 'DashboardPage'),
})
