import { createFileRoute } from '@tanstack/react-router'

import { SessionsListPage } from '@/features/sessions/pages/SessionsListPage'

export const Route = createFileRoute('/_app/sessions/')({
  component: SessionsListPage,
})
