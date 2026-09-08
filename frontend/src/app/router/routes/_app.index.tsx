import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { DashboardPage } from '@/features/dashboard/pages/DashboardPage'

const dashboardSearchSchema = z.object({
  source: z.string().optional(),
  agent: z.string().optional(),
  model: z.string().optional(),
  period: z.enum(['24h', '7d', '30d']).optional().default('7d'),
})

export const Route = createFileRoute('/_app/')({
  validateSearch: dashboardSearchSchema,
  component: DashboardPage,
})
