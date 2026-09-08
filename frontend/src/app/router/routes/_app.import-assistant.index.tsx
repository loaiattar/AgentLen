import { createFileRoute } from '@tanstack/react-router'

import { ImportAssistantPage } from '@/features/import-assistant/pages/ImportAssistantPage'

export const Route = createFileRoute('/_app/import-assistant/')({
  component: ImportAssistantPage,
})
