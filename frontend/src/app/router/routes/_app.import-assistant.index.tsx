import { createFileRoute, lazyRouteComponent } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/import-assistant/')({
  component: lazyRouteComponent(() => import('@/features/import-assistant/pages/ImportAssistantPage'), 'ImportAssistantPage'),
})
