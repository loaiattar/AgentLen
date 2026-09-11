import { createFileRoute, redirect } from '@tanstack/react-router'

import { AppLayout } from '@/app/layouts/AppLayout'
import { parseMetricsSearch } from '@/features/dashboard/lib/filters'
import { getSessionToken } from '@/lib/auth/session'

export const Route = createFileRoute('/_app')({
  validateSearch: parseMetricsSearch,
  beforeLoad: ({ location }) => {
    if (!getSessionToken()) {
      throw redirect({
        to: '/login',
        search: { redirect: location.pathname },
      })
    }
  },
  component: AppLayout,
})
