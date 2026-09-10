import type { MappingDocument } from '@/features/mappings/types'

export type {
  MappingDocument,
  MappingEntity,
  MappingFieldRule,
} from '@/features/mappings/types'

export interface AiProvidersResponse {
  active: { provider: string; model: string | null }
  available: Array<{ provider: string; configured: boolean }>
}

export interface FileUpload {
  id: number
  original_name: string
  format: string
  size_bytes: number
  content_hash: string
  already_seen: boolean
  previous_import_run_ids: number[]
}

export interface FieldProfile {
  path: string
  types: string[]
  null_ratio: number
  distinct_ratio: number | null
  min: string | null
  max: string | null
  examples: string[]
}

export interface FileProfile {
  file_id: number
  record_count: number
  sampled_records: number
  fields: FieldProfile[]
}

export interface ValidationError {
  code?: string
  field_path?: string | null
  message: string
}

export interface ProposalValidation {
  valid: boolean
  errors: ValidationError[]
}

export interface ProposalRationale {
  target?: string
  source?: string
  confidence?: string | number
  explanation?: string
}

export interface ProposalAmbiguity {
  field?: string
  question?: string
  options?: string[]
}

export interface UnmappedField {
  path?: string
  reason?: string
}

export interface ProposalResponse {
  proposal_id: number
  analyzer: Record<string, unknown>
  mapping: MappingDocument
  validation: ProposalValidation
  rationale: ProposalRationale[]
  ambiguities: ProposalAmbiguity[]
  unmapped_fields: UnmappedField[]
}

export interface ImportPreview {
  sampled: number
  would_import: Record<string, number>
  would_reject: number
  entities: Array<{ target: string; rows: Array<Record<string, unknown>> }>
  issues: Array<{
    line_number: number | null
    severity: string
    code: string
    message: string
    field_path: string | null
  }>
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}
