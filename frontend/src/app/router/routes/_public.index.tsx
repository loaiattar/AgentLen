import { createFileRoute, lazyRouteComponent } from '@tanstack/react-router'

export const Route = createFileRoute('/_public/')({
  component: lazyRouteComponent(() => import('@/features/landing/pages/LandingPage'), 'LandingPage'),
})
