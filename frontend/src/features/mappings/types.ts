/**
 * Wire shapes for the mapping routes — `interfaces/http/schemas/mappings.py`
 * (API.md §4, MAPPING_CONTRACT.md §2).
 *
 * Two different things are called a version and they must not be shown as one:
 *
 *  - `Mapping.version` (an integer) is the storage revision the repository
 *    owns. It is what `GET /mappings` returns and what the UI means by `v3`.
 *  - `mapping_version` (the string `"1.0"`, carried inside a document by
 *    `mapping_to_document()`) is the version of the document *format*. It never
 *    identifies a saved mapping and must never be rendered as one.
 */

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
  /** JSONPath that turns one record into N rows. */
  iterate?: string | null
  parent?: Record<string, unknown> | null
}

/** `MappingDocumentIn` — the document alone, without the storage metadata. */
export interface MappingDocument {
  source_format: string
  entities: MappingEntity[]
}

/**
 * `MappingOut`. `status` is a free string backend-side (`mappings.py` filters
 * on it without a whitelist), so it is not narrowed here: an unknown lifecycle
 * value must render, not break the select.
 */
export interface Mapping extends MappingDocument {
  id: number
  data_source_id: number
  name: string
  version: number
  status: string
  created_at: string
}

/**
 * `MappingCreateIn`. This is the shape that promotes an AI proposal into a
 * saved mapping: `POST /mappings/proposals` answers a `proposal_id`, which no
 * route turns into a mapping on its own — the assistant has to send the
 * proposal's document here to obtain the `mapping_id` an import needs.
 */
export interface MappingCreateRequest extends MappingDocument {
  data_source_id: number
  name: string
}
