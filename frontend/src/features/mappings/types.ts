export interface MappingFieldRule {
  target: string
  source: string
  required: boolean
  operators: Array<Record<string, unknown>>
}

export interface MappingEntity {
  target: string
  natural_key: string[]
  fields: MappingFieldRule[]
  iterate: string | null
  parent: Record<string, unknown> | null
}

export interface MappingDocument {
  mapping_version?: string
  name: string
  source_format: 'jsonl' | 'csv' | 'parquet' | string
  entities: MappingEntity[]
}

export interface SavedMapping {
  id: number
  data_source_id: number
  name: string
  version: number
  source_format: string
  status: string
}

export interface MappingCreateInput {
  data_source_id: number
  name: string
  source_format: string
  entities: MappingEntity[]
}
