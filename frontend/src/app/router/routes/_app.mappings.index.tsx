import { createFileRoute, lazyRouteComponent } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/mappings/')({
  component: lazyRouteComponent(() => import('@/features/mappings/pages/MappingsListPage'), 'MappingsListPage'),
})
