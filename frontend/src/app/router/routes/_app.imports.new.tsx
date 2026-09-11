import { createFileRoute, lazyRouteComponent } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/imports/new')({
  component: lazyRouteComponent(() => import('@/features/imports/pages/ImportWizardPage'), 'ImportWizardPage'),
})
