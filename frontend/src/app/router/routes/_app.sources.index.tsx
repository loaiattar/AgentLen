import { createFileRoute, lazyRouteComponent } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/sources/')({
  component: lazyRouteComponent(() => import('@/features/sources/pages/SourcesListPage'), 'SourcesListPage'),
})
