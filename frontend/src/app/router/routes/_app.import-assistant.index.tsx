import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { ImportAssistantPage } from '@/features/import-assistant/pages/ImportAssistantPage'

const importAssistantSearchSchema = z.object({
  importId: z.string().optional(),
})

export const Route = createFileRoute('/_app/import-assistant/')({
  validateSearch: importAssistantSearchSchema,
  component: ImportAssistantPage,
})
