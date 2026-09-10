/**
 * Wire shapes for the import workflow.
 *
 * Mirrors the backend schemas one-to-one — `interfaces/http/schemas/files.py`
 * (API.md §2), `schemas/imports.py` (API.md §5) and `schemas/data_sources.py`.
 * Nothing here is reshaped: a field the API can omit is optional here too, so a
 * missing value stays distinguishable from a zero (ARCHITECTURE §2).
 */

/** Envelope of every list endpoint (`schemas/common.py`). */
export interface Page<T> {
  items: T[]
  /** Total matching rows, ignoring limit and offset. */
  total: number
  limit: number
  offset: number
}

export interface PageParams {
  limit?: number
  offset?: number
}

// --- Data sources (API.md §2) ------------------------------------------------

export interface DataSource {
  id: number
  slug: string
  name: string
  description: string | null
  url: string | null
  license: string | null
  dataset_version: string | null
  retrieved_at: string | null
  created_at: string
}

// --- Files (API.md §2) -------------------------------------------------------

export type FileFormat = 'jsonl' | 'csv' | 'parquet'

export interface FileUpload {
  id: number
  original_name: string
  /** Detected server-side from the magic bytes, not from the extension. */
  format: FileFormat
  size_bytes: number
  content_hash: string
  /** True when this exact content was already stored — warn before re-importing. */
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
  /** The file's real row count. */
  record_count: number
  /** How many rows the profile actually looked at — bounded, unlike `record_count`. */
  sampled_records: number
  fields: FieldProfile[]
}

// --- Mappings (API.md §4) ----------------------------------------------------

export type MappingStatus = 'draft' | 'validated' | 'active' | 'superseded' | 'rejected' | 'archived'

/**
 * The subset of a mapping this workflow needs to let the user pick one.
 * The full document belongs to the mappings feature (#32 / #52).
 */
export interface MappingSummary {
  id: number
  name: string
  version: number
  status: MappingStatus
  data_source_id: number | null
}

// --- Imports (API.md §5) -----------------------------------------------------

export type ImportSeverity = 'rejected' | 'duplicate' | 'warning'

export interface ImportIssue {
  line_number: number | null
  severity: ImportSeverity
  code: string
  message: string
  field_path: string | null
}

export interface ImportPreviewRequest {
  file_id: number
  mapping_id: number
  sample_size?: number
}

export interface PreviewEntities {
  target: string
  rows: Record<string, unknown>[]
}

export interface ImportPreview {
  sampled: number
  /** Entity target -> how many rows would be written. */
  would_import: Record<string, number>
  would_reject: number
  entities: PreviewEntities[]
  issues: ImportIssue[]
}

export interface ImportCreateRequest {
  data_source_id: number
  file_upload_id: number
  mapping_id: number
}

export interface ImportCreateResponse {
  import_run_id: number
  status: ImportRunStatus
}

/** Matches the `import_run.status` check constraint. */
export type ImportRunStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'partial'
  | 'failed'
  | 'cancelled'

export interface ImportReport {
  records_read: number
  records_imported: number
  records_duplicate: number
  records_rejected: number
  /** Field -> how many records were missing it. Null when not computed. */
  fields_missing: Record<string, number> | null
}

export interface DataSourceRef {
  id: number
  slug: string
}

export interface FileRef {
  id: number
  original_name: string
}

export interface MappingRef {
  id: number
  name: string
  version: number
}

export interface ImportStatus {
  id: number
  status: ImportRunStatus
  data_source: DataSourceRef
  file: FileRef
  mapping: MappingRef
  report: ImportReport
  started_at: string | null
  finished_at: string | null
}

/** A run the worker has finished with — nothing left to poll for. */
export const TERMINAL_STATUSES = ['succeeded', 'partial', 'failed', 'cancelled'] as const

export function isTerminal(status: ImportRunStatus): boolean {
  return (TERMINAL_STATUSES as readonly string[]).includes(status)
}
