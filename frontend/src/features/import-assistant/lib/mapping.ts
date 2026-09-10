import type { MappingDocument, ProposalRationale } from '@/features/import-assistant/types'

export function confidencePercent(value: string | number | undefined): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.round(value <= 1 ? value * 100 : value)
  }
  if (value === 'high') return 90
  if (value === 'medium') return 60
  if (value === 'low') return 35
  return undefined
}

export function rationaleBody(item: ProposalRationale): string {
  const parts = [item.explanation, item.source ? `from ${item.source}` : null].filter(Boolean)
  return parts.join(' · ') || 'The assistant did not explain this mapping.'
}

export function describeOperators(operators: Array<Record<string, unknown>> | undefined): string {
  if (operators == null || operators.length === 0) return 'none'
  return operators
    .map((operator) => {
      const op = typeof operator.op === 'string' ? operator.op : 'op'
      const extra = typeof operator.to === 'string' ? ` → ${operator.to}` : ''
      return `${op}${extra}`
    })
    .join(', ')
}

export function fieldConfidence(
  rationale: ProposalRationale[],
  entityTarget: string,
  fieldTarget: string,
): number | undefined {
  const match = rationale.find(
    (item) => item.target === `${entityTarget}.${fieldTarget}` || item.target === fieldTarget,
  )
  return confidencePercent(match?.confidence)
}

export function updateFieldSource(
  mapping: MappingDocument,
  entityTarget: string,
  fieldTarget: string,
  source: string,
): MappingDocument {
  return {
    ...mapping,
    entities: mapping.entities.map((entity) =>
      entity.target !== entityTarget
        ? entity
        : {
            ...entity,
            fields: entity.fields.map((field) =>
              field.target !== fieldTarget ? field : { ...field, source },
            ),
          },
    ),
  }
}
