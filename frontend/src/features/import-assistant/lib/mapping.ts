import type {
  MappingDocument,
  MappingProposalDocument,
  ProposalRationale,
  ProposalResponse,
} from '@/features/import-assistant/types'

const CONFIDENCE_LABELS = ['high', 'medium', 'low'] as const
export type ConfidenceLabel = (typeof CONFIDENCE_LABELS)[number]

/**
 * The label the agent returned (`prompts/analysis.py` asks for high, medium or
 * low), shown as is. It is not a measure, so it never becomes a percentage;
 * anything else — a number, free text — is not shown at all.
 */
export function confidenceLabel(value: string | number | undefined): ConfidenceLabel | undefined {
  const label = typeof value === 'string' ? value.trim().toLowerCase() : undefined
  return CONFIDENCE_LABELS.find((known) => known === label)
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
): ConfidenceLabel | undefined {
  const match = rationale.find(
    (item) => item.target === `${entityTarget}.${fieldTarget}` || item.target === fieldTarget,
  )
  return confidenceLabel(match?.confidence)
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

interface FieldSignature {
  source: string
  required: boolean
  /** Rendered form, for the status text. */
  operators: string
  /** Raw form, for equality — `describeOperators` only shows `op` and `to`. */
  operatorsKey: string
}

interface EntitySignature {
  naturalKey: string
  iterate: string
}

function fieldSignatures(mapping: MappingDocument): Map<string, FieldSignature> {
  const signatures = new Map<string, FieldSignature>()
  for (const entity of mapping.entities) {
    for (const field of entity.fields) {
      signatures.set(`${entity.target}.${field.target}`, {
        source: field.source ?? '',
        required: field.required === true,
        operators: describeOperators(field.operators),
        operatorsKey: JSON.stringify(field.operators ?? []),
      })
    }
  }
  return signatures
}

function entitySignatures(mapping: MappingDocument): Map<string, EntitySignature> {
  const signatures = new Map<string, EntitySignature>()
  for (const entity of mapping.entities) {
    signatures.set(entity.target, {
      naturalKey: (entity.natural_key ?? []).join(', ') || 'none',
      iterate: entity.iterate ?? 'none',
    })
  }
  return signatures
}

function union<T>(left: Iterable<T>, right: Iterable<T>): Set<T> {
  return new Set([...left, ...right])
}

/**
 * Every part of the document the studio can show, not just `source`: a status
 * turn that says nothing changed while the Operators line next to it reads
 * `to_int` is a lie the chat must not tell.
 */
function diffMappings(before: MappingProposalDocument, after: MappingProposalDocument): string[] {
  const changes: string[] = []

  if (before.name !== after.name) changes.push(`name: ${before.name} → ${after.name}`)
  if (before.source_format !== after.source_format) {
    changes.push(`source format: ${before.source_format} → ${after.source_format}`)
  }

  const previousEntities = entitySignatures(before)
  const nextEntities = entitySignatures(after)
  const gone = new Set<string>()
  for (const target of union(previousEntities.keys(), nextEntities.keys())) {
    const from = previousEntities.get(target)
    const to = nextEntities.get(target)
    if (from == null) {
      changes.push(`${target} entity added`)
      gone.add(target)
      continue
    }
    if (to == null) {
      changes.push(`${target} entity removed`)
      gone.add(target)
      continue
    }
    if (from.naturalKey !== to.naturalKey) {
      changes.push(`${target} natural key: ${from.naturalKey} → ${to.naturalKey}`)
    }
    if (from.iterate !== to.iterate) changes.push(`${target} iterate: ${from.iterate} → ${to.iterate}`)
  }

  const previousFields = fieldSignatures(before)
  const nextFields = fieldSignatures(after)
  for (const key of union(previousFields.keys(), nextFields.keys())) {
    // An added or removed entity already accounts for all of its fields.
    if (gone.has(key.slice(0, key.indexOf('.')))) continue
    const from = previousFields.get(key)
    const to = nextFields.get(key)
    if (from == null) {
      changes.push(`${key} added (${to?.source || 'no source'})`)
      continue
    }
    if (to == null) {
      changes.push(`${key} removed`)
      continue
    }
    if (from.source !== to.source) {
      changes.push(`${key}: ${from.source || 'none'} → ${to.source || 'none'}`)
    }
    if (from.required !== to.required) {
      changes.push(`${key} ${to.required ? 'now required' : 'no longer required'}`)
    }
    if (from.operatorsKey !== to.operatorsKey) {
      changes.push(
        from.operators === to.operators
          ? `${key} operator options changed`
          : `${key} operators: ${from.operators} → ${to.operators}`,
      )
    }
  }

  return changes
}

/** Status text from two API proposals. Never claims an update that did not happen. */
export function describeProposalChange(before: ProposalResponse, after: ProposalResponse): string {
  const changes = diffMappings(before.mapping, after.mapping)

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
  const mappingLine = `Applied ${changes.length} change(s). ${preview}${extra}`
  return validationLine ? `${mappingLine} ${validationLine}` : mappingLine
}
