import type { MetricsPeriod } from '@/features/dashboard/lib/filters'

export interface DashboardFilters {
  data_source_id?: number
  agent_id?: number
  model_id?: number
  tool_id?: number
  import_run_id?: number
  date_from?: string
  date_to?: string
  status?: string
  /** Kept as a period, not as dates, until a request is sent (`resolvePeriod`). */
  period?: MetricsPeriod
}

export interface Coverage {
  present: number
  total: number
  ratio: number | null
}

export interface Metric {
  key: string
  value: number | null
  unit: string
  coverage: Coverage
  warning: string | null
}

export interface OverviewResponse {
  filters_applied: Record<string, unknown>
  metrics: Metric[]
}

export interface MetricDefinition {
  key: string
  label: string
  unit: string
  formula: string
  scope: string
  missing_policy: string
  comparability: 'cross_source' | 'per_source_only'
}

export interface DefinitionsResponse {
  definitions: MetricDefinition[]
}

export interface ActivityPoint {
  day: string
  data_source_id: number
  session_count: number
  model_call_count: number
  tool_call_count: number
  input_tokens: number | null
  output_tokens: number | null
  coverage: Coverage
  filters: Record<string, unknown>
}

export interface ToolPoint {
  label: string
  tool_id: number
  data_source_id: number
  call_count: number
  error_count: number
  error_ratio: number | null
  coverage: Coverage
  filters: Record<string, unknown>
}

export interface ModelPoint {
  label: string
  model_id: number | null
  provider_name: string | null
  data_source_id: number
  call_count: number
  input_tokens: number | null
  output_tokens: number | null
  coverage: Coverage
  cache_read_tokens: number | null
  cache_coverage: Coverage
  filters: Record<string, unknown>
}

export interface QualityPoint {
  import_run_id: number
  data_source_id: number
  status: string
  records_read: number
  records_imported: number
  records_duplicate: number
  records_rejected: number
  issue_count: number
  rejection_ratio: number | null
  fields_missing: Record<string, number>
  filters: Record<string, unknown>
}

export interface PointsResponse<T> {
  points: T[]
  filters_applied: Record<string, unknown>
  warnings: string[]
}
