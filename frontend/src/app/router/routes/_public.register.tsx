import { createFileRoute, lazyRouteComponent, redirect } from '@tanstack/react-router'

import { parseAuthRedirectSearch } from '@/features/auth/lib/redirect'
import { getSessionToken } from '@/lib/auth/session'

export const Route = createFileRoute('/_public/register')({
  validateSearch: parseAuthRedirectSearch,
  beforeLoad: () => {
    if (getSessionToken()) {
      throw redirect({ to: '/overview' })
    }
  },
  component: lazyRouteComponent(() => import('@/features/auth/pages/RegisterPage'), 'RegisterPage'),
})
