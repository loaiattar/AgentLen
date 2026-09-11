import { createFileRoute, redirect } from '@tanstack/react-router'

import { RegisterPage } from '@/features/auth/pages/RegisterPage'
import { parseAuthRedirectSearch } from '@/features/auth/lib/redirect'
import { getSessionToken } from '@/lib/auth/session'

export const Route = createFileRoute('/_public/register')({
  validateSearch: parseAuthRedirectSearch,
  beforeLoad: () => {
    if (getSessionToken()) {
      throw redirect({ to: '/overview' })
    }
  },
  component: RegisterPage,
})
