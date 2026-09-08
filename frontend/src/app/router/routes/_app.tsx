import { createFileRoute } from '@tanstack/react-router'

import { AppLayout } from '@/app/layouts/AppLayout'

export const Route = createFileRoute('/_app')({
  component: AppLayout,
})
