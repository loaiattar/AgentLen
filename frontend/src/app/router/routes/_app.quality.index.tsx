import { createFileRoute } from '@tanstack/react-router'

import { DataQualityPage } from '@/features/quality/pages/DataQualityPage'

export const Route = createFileRoute('/_app/quality/')({
  component: DataQualityPage,
})
