import type { MappingProposalDocument } from '@/features/mappings/types'

export type {
  MappingDocument,
  MappingEntity,
  MappingFieldRule,
  MappingProposalDocument,
} from '@/features/mappings/types'
export type { FileProfile, FileUpload, ImportPreview } from '@/features/imports/types'

export interface AiProvidersResponse {
  active: { provider: string; model: string | null }
  available: Array<{ provider: string; configured: boolean }>
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
  mapping: MappingProposalDocument
  validation: ProposalValidation
  rationale: ProposalRationale[]
  ambiguities: ProposalAmbiguity[]
  unmapped_fields: UnmappedField[]
}

export interface ChatTurn {
  role: 'user' | 'status'
  content: string
}
