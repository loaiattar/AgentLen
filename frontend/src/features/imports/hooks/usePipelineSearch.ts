import { getRouteApi, useNavigate } from '@tanstack/react-router'
import { useCallback } from 'react'

import type { MetricsSearch } from '@/features/dashboard/lib/filters'

const appRoute = getRouteApi('/_app')

/**
 * Leaf routes that share the import pipeline ids (`file_id`, `mapping_id`,
 * `proposal_id`). `_app` is pathless (`fullPath: '/'`): a search-only
 * `navigate` from the layout would bounce to Overview, so callers must stay
 * on a leaf.
 */
export type PipelineRoute = '/imports/new' | '/import-assistant'

export function withFileId(prev: MetricsSearch, fileId: number | undefined): MetricsSearch {
  const next: MetricsSearch = { ...prev }
  delete next.proposal_id
  delete next.mapping_id
  if (fileId == null) delete next.file_id
  else next.file_id = fileId
  return next
}

export function withProposalId(prev: MetricsSearch, proposalId: number | undefined): MetricsSearch {
  const next: MetricsSearch = { ...prev }
  if (proposalId == null) delete next.proposal_id
  else next.proposal_id = proposalId
  return next
}

export function withMappingId(prev: MetricsSearch, mappingId: number | undefined): MetricsSearch {
  const next: MetricsSearch = { ...prev }
  if (mappingId == null) delete next.mapping_id
  else next.mapping_id = mappingId
  return next
}

export function withPipelineDataSource(
  prev: MetricsSearch,
  dataSourceId: number | undefined,
): MetricsSearch {
  const next: MetricsSearch = { ...prev }
  delete next.mapping_id
  if (dataSourceId == null) delete next.data_source_id
  else next.data_source_id = dataSourceId
  return next
}

/**
 * Source of truth for the file → mapping → import hand-off. Studio and wizard
 * both read these ids; whoever writes them stays on its own leaf so the other
 * page can resume from the URL instead of local state.
 */
export function usePipelineSearch(to: PipelineRoute) {
  const search = appRoute.useSearch()
  const navigate = useNavigate()

  const patchSearch = useCallback(
    (patch: (prev: MetricsSearch) => MetricsSearch) => {
      void navigate({ to, search: patch })
    },
    [navigate, to],
  )

  const setFileId = useCallback(
    (fileId: number | undefined) => {
      patchSearch((prev) => withFileId(prev, fileId))
    },
    [patchSearch],
  )

  const setProposalId = useCallback(
    (proposalId: number | undefined) => {
      patchSearch((prev) => withProposalId(prev, proposalId))
    },
    [patchSearch],
  )

  const setMappingId = useCallback(
    (mappingId: number | undefined) => {
      patchSearch((prev) => withMappingId(prev, mappingId))
    },
    [patchSearch],
  )

  const setDataSourceId = useCallback(
    (dataSourceId: number | undefined) => {
      patchSearch((prev) => withPipelineDataSource(prev, dataSourceId))
    },
    [patchSearch],
  )

  return {
    fileId: search.file_id,
    proposalId: search.proposal_id,
    mappingId: search.mapping_id,
    dataSourceId: search.data_source_id,
    setFileId,
    setProposalId,
    setMappingId,
    setDataSourceId,
  }
}
