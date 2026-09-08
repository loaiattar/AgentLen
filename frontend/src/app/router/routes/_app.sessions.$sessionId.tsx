import { createFileRoute } from '@tanstack/react-router'

import { SessionDetailPage } from '@/features/sessions/pages/SessionDetailPage'

export const Route = createFileRoute('/_app/sessions/$sessionId')({
  component: SessionDetailPage,
})
