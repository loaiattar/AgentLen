import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { describeOperators, fieldConfidence } from '@/features/import-assistant/lib/mapping'
import type { MappingProposalDocument, ProposalRationale } from '@/features/import-assistant/types'

export interface MappingColumnProps {
  mapping: MappingProposalDocument
  rationale: ProposalRationale[]
  dirty: boolean
  saving: boolean
  locked: boolean
  onSourceChange: (entity: string, target: string, source: string) => void
  onSaveEdits: () => void
}

export function MappingColumn({
  mapping,
  rationale,
  dirty,
  saving,
  locked,
  onSourceChange,
  onSaveEdits,
}: MappingColumnProps) {
  return (
    <section className="glass-module order-1 p-6 xl:order-2">
      <div className="mb-2 flex items-start justify-between gap-3">
        <h2 className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">Mapping</h2>
        {dirty && !locked ? (
          <Button type="button" variant="secondary" size="sm" loading={saving} onClick={onSaveEdits}>
            Save edits
          </Button>
        ) : null}
      </div>
      <p className="text-secondary text-foreground-muted">
        {mapping.name} · {mapping.source_format}
      </p>
      <ul className="mt-6 grid gap-6">
        {mapping.entities.flatMap((entity) =>
          entity.fields.map((field) => {
            const confidence = fieldConfidence(rationale, entity.target, field.target)
            return (
              <li key={`${entity.target}-${field.target}`} className="grid gap-2">
                <p className="text-body text-foreground">
                  {entity.target}.{field.target}
                </p>
                <Input
                  value={field.source ?? ''}
                  disabled={locked}
                  aria-label={`Source for ${entity.target}.${field.target}`}
                  onChange={(event) => onSourceChange(entity.target, field.target, event.target.value)}
                />
                <p className="text-meta text-foreground-subtle">{describeOperators(field.operators)}</p>
                {confidence != null ? (
                  <p className="text-meta text-accent-magenta">Confidence: {confidence}</p>
                ) : null}
              </li>
            )
          }),
        )}
      </ul>
    </section>
  )
}
