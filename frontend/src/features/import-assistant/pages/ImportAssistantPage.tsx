import { getRouteApi } from '@tanstack/react-router'

import { TwoColumnTemplate } from '@/components/templates/TwoColumnTemplate'
import { useSendAssistantMessageMutation } from '@/features/import-assistant/api/import-assistant.mutations'
import { ChatPanel } from '@/features/import-assistant/components/ChatPanel'
import { MappingDraftPreview } from '@/features/import-assistant/components/MappingDraftPreview'
import { useValidateMappingDraft } from '@/features/import-assistant/hooks/useValidateMappingDraft'
import { useImportAssistantStore } from '@/features/import-assistant/store/import-assistant.store'

const routeApi = getRouteApi('/_app/import-assistant/')

export function ImportAssistantPage() {
  const { importId } = routeApi.useSearch()
  const messages = useImportAssistantStore((state) => state.messages)
  const draftName = useImportAssistantStore((state) => state.draftName)
  const draftFields = useImportAssistantStore((state) => state.draftFields)
  const addMessage = useImportAssistantStore((state) => state.addMessage)
  const setDraftName = useImportAssistantStore((state) => state.setDraftName)
  const setDraftFields = useImportAssistantStore((state) => state.setDraftFields)

  const sendMessage = useSendAssistantMessageMutation()
  const { validate, isPending } = useValidateMappingDraft()

  const handleSend = (content: string) => {
    if (!importId) return
    addMessage({ id: crypto.randomUUID(), role: 'user', content })
    sendMessage.mutate(
      { importId, message: content },
      {
        onSuccess: (response) => {
          addMessage(response.reply)
          if (response.suggestedFields) setDraftFields(response.suggestedFields)
        },
      },
    )
  }

  return (
    <TwoColumnTemplate
      main={<ChatPanel messages={messages} onSend={handleSend} isSending={sendMessage.isPending} />}
      side={
        <MappingDraftPreview
          name={draftName}
          fields={draftFields}
          onNameChange={setDraftName}
          onValidate={validate}
          isValidating={isPending}
        />
      }
    />
  )
}
