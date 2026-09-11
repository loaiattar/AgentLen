import { createFileRoute } from '@tanstack/react-router'

import { ImportWizardPage } from '@/features/imports/pages/ImportWizardPage'

export const Route = createFileRoute('/_app/imports/new')({
  component: ImportWizardPage,
})
