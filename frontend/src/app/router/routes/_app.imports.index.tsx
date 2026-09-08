import { createFileRoute } from '@tanstack/react-router'

import { ImportListPage } from '@/features/imports/pages/ImportListPage'

export const Route = createFileRoute('/_app/imports/')({
  component: ImportListPage,
})
