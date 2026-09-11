import { createFileRoute, redirect } from '@tanstack/react-router'

import { LoginPage } from '@/features/auth/pages/LoginPage'
import { parseAuthRedirectSearch } from '@/features/auth/lib/redirect'
import { getSessionToken } from '@/lib/auth/session'

export const Route = createFileRoute('/_public/login')({
  validateSearch: parseAuthRedirectSearch,
  beforeLoad: () => {
    if (getSessionToken()) {
      throw redirect({ to: '/overview' })
    }
  },
  component: LoginPage,
})
