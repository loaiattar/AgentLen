import { createFileRoute, lazyRouteComponent } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/sessions/')({
  component: lazyRouteComponent(() => import('@/features/sessions/pages/SessionsListPage'), 'SessionsListPage'),
})
