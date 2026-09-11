import { createFileRoute, lazyRouteComponent } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/imports/')({
  component: lazyRouteComponent(() => import('@/features/imports/pages/ImportListPage'), 'ImportListPage'),
})
