import { Button } from '@/components/atoms/Button'
import { Input } from '@/components/atoms/Input'
import { FormField } from '@/components/molecules/FormField'
import type { DraftMappingField } from '@/features/import-assistant/types'

export interface MappingDraftPreviewProps {
  name: string
  fields: DraftMappingField[]
  onNameChange: (name: string) => void
  onValidate: () => void
  isValidating?: boolean
}

export function MappingDraftPreview({
  name,
  fields,
  onNameChange,
  onValidate,
  isValidating,
}: MappingDraftPreviewProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-3">
      <FormField label="Nom du mapping" htmlFor="mapping-name">
        <Input id="mapping-name" value={name} onChange={(event) => onNameChange(event.target.value)} />
      </FormField>

      <ul className="flex flex-col gap-1 text-sm">
        {fields.map((field) => (
          <li key={`${field.sourceField}-${field.targetField}`} className="flex justify-between gap-2">
            <span className="text-muted-foreground">{field.sourceField}</span>
            <span>→ {field.targetField}</span>
          </li>
        ))}
        {fields.length === 0 && <li className="text-muted-foreground">Aucun champ suggéré pour l'instant.</li>}
      </ul>

      <Button onClick={onValidate} disabled={isValidating || fields.length === 0}>
        {isValidating ? 'Validation…' : 'Valider le mapping'}
      </Button>
    </div>
  )
}
