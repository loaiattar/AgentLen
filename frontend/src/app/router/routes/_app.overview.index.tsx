import { createFileRoute } from '@tanstack/react-router'

import { DashboardPage } from '@/features/dashboard/pages/DashboardPage'

export const Route = createFileRoute('/_app/overview/')({
  component: DashboardPage,
})
