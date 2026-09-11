import { describe, expect, it } from 'vitest'

import {
  withFileId,
  withMappingId,
  withPipelineDataSource,
  withProposalId,
} from '@/features/imports/hooks/usePipelineSearch'

/**
 * These four carry the pipeline's cascade rule: choosing something upstream
 * invalidates everything downstream of it. A stale `mapping_id` surviving a
 * file change is how a user previews one file and imports another, so the rule
 * is pinned here rather than left to each caller to remember.
 */
describe('withFileId', () => {
  it('drops the proposal and the mapping — they belonged to the previous file', () => {
    const next = withFileId({ file_id: 1, proposal_id: 7, mapping_id: 9 }, 2)

    expect(next).toEqual({ file_id: 2 })
  })

  it('clears the file itself when given nothing', () => {
    expect(withFileId({ file_id: 1, mapping_id: 9 }, undefined)).toEqual({})
  })

  it('leaves unrelated search untouched', () => {
    const next = withFileId({ data_source_id: 4, file_id: 1 }, 2)

    expect(next.data_source_id).toBe(4)
  })

  it('does not mutate the search it was given', () => {
    const previous = { file_id: 1, mapping_id: 9 }

    withFileId(previous, 2)

    expect(previous).toEqual({ file_id: 1, mapping_id: 9 })
  })
})

describe('withPipelineDataSource', () => {
  it('drops the mapping — mappings are scoped to a source', () => {
    const next = withPipelineDataSource({ data_source_id: 1, mapping_id: 9 }, 2)

    expect(next).toEqual({ data_source_id: 2 })
  })

  it('keeps the file: a file does not belong to a source until it is imported', () => {
    const next = withPipelineDataSource({ file_id: 3, data_source_id: 1 }, 2)

    expect(next.file_id).toBe(3)
  })

  it('drops the mapping even when the source is cleared', () => {
    expect(withPipelineDataSource({ data_source_id: 1, mapping_id: 9 }, undefined)).toEqual({})
  })
})

describe('withMappingId and withProposalId', () => {
  it('sets and clears without touching anything else', () => {
    expect(withMappingId({ file_id: 1 }, 5)).toEqual({ file_id: 1, mapping_id: 5 })
    expect(withMappingId({ file_id: 1, mapping_id: 5 }, undefined)).toEqual({ file_id: 1 })
    expect(withProposalId({ file_id: 1 }, 8)).toEqual({ file_id: 1, proposal_id: 8 })
    expect(withProposalId({ file_id: 1, proposal_id: 8 }, undefined)).toEqual({ file_id: 1 })
  })

  it('treats null like undefined — the router hands back either', () => {
    expect(withMappingId({ mapping_id: 5 }, null as never)).toEqual({})
    expect(withProposalId({ proposal_id: 8 }, null as never)).toEqual({})
  })
})
