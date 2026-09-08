import { useCreateMappingMutation } from '@/features/mappings/api/mappings.mutations'
import { useImportAssistantStore } from '@/features/import-assistant/store/import-assistant.store'

export function useValidateMappingDraft() {
  const draftName = useImportAssistantStore((state) => state.draftName)
  const draftFields = useImportAssistantStore((state) => state.draftFields)
  const reset = useImportAssistantStore((state) => state.reset)
  const createMapping = useCreateMappingMutation()

  const validate = () =>
    createMapping.mutate(
      { name: draftName, fields: draftFields },
      { onSuccess: () => reset() },
    )

  return { validate, isPending: createMapping.isPending, error: createMapping.error }
}
