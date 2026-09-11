import type { MappingDocument, ProposalRationale, ProposalResponse } from '@/features/import-assistant/types'

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

export function updateFieldSource<T extends MappingDocument>(
  mapping: T,
  entityTarget: string,
  fieldTarget: string,
  source: string,
): T {
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

function fieldSources(mapping: MappingDocument): Map<string, string> {
  const sources = new Map<string, string>()
  for (const entity of mapping.entities) {
    for (const field of entity.fields) {
      sources.set(`${entity.target}.${field.target}`, field.source ?? '')
    }
  }
  return sources
}

/** Status text from two API proposals. Never claims an update that did not happen. */
export function describeProposalChange(before: ProposalResponse, after: ProposalResponse): string {
  const previous = fieldSources(before.mapping)
  const next = fieldSources(after.mapping)
  const keys = new Set([...previous.keys(), ...next.keys()])
  const changes: string[] = []

  for (const key of keys) {
    const from = previous.get(key)
    const to = next.get(key)
    if (from === to) continue
    if (from == null) changes.push(`${key} added (${to})`)
    else if (to == null) changes.push(`${key} removed`)
    else changes.push(`${key}: ${from} → ${to}`)
  }

  const validationNow = after.validation.valid
  const validationWas = before.validation.valid
  const validationLine =
    validationNow === validationWas
      ? null
      : validationNow
        ? 'Validation now passes.'
        : `Validation failed${after.validation.errors[0]?.message ? `: ${after.validation.errors[0].message}` : '.'}`

  if (changes.length === 0) {
    return validationLine ? `The mapping did not change. ${validationLine}` : 'The mapping did not change.'
  }

  const preview = changes.slice(0, 3).join('; ')
  const extra = changes.length > 3 ? ` (+${changes.length - 3} more)` : ''
  const mappingLine = `Updated ${changes.length} field source(s). ${preview}${extra}`
  return validationLine ? `${mappingLine} ${validationLine}` : mappingLine
}
