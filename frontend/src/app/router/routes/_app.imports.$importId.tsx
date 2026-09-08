import { createFileRoute } from '@tanstack/react-router'

import { ImportDetailPage } from '@/features/imports/pages/ImportDetailPage'

export const Route = createFileRoute('/_app/imports/$importId')({
  component: ImportDetailPage,
})
