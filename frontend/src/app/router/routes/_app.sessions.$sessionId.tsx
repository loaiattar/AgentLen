import { createFileRoute, lazyRouteComponent } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/sessions/$sessionId')({
  component: lazyRouteComponent(() => import('@/features/sessions/pages/SessionDetailPage'), 'SessionDetailPage'),
})
