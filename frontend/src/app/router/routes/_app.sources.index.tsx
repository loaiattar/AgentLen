import { createFileRoute } from '@tanstack/react-router'

import { SourcesListPage } from '@/features/sources/pages/SourcesListPage'

export const Route = createFileRoute('/_app/sources/')({
  component: SourcesListPage,
})
