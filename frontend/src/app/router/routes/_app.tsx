import { createFileRoute } from '@tanstack/react-router'

import { AppLayout } from '@/app/layouts/AppLayout'
import { parseMetricsSearch } from '@/features/dashboard/lib/filters'

export const Route = createFileRoute('/_app')({
  validateSearch: parseMetricsSearch,
  component: AppLayout,
})
