import { createFileRoute, lazyRouteComponent } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/imports/$importId')({
  component: lazyRouteComponent(() => import('@/features/imports/pages/ImportDetailPage'), 'ImportDetailPage'),
})
