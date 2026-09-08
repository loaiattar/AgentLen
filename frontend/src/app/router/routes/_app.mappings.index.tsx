import { createFileRoute } from '@tanstack/react-router'

import { MappingsListPage } from '@/features/mappings/pages/MappingsListPage'

export const Route = createFileRoute('/_app/mappings/')({
  component: MappingsListPage,
})
