/**
 * Shapes shared by every feature that talks to the API.
 *
 * They live here rather than in one feature's `types.ts` because more than one
 * feature reads the same list routes: `features/imports` paginates import runs,
 * `features/mappings` paginates mappings, and neither should have to import
 * from the other to name the envelope they both receive.
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
