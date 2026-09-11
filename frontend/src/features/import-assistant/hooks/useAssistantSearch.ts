import { getRouteApi, useNavigate } from '@tanstack/react-router'

import type { MetricsSearch } from '@/features/dashboard/lib/filters'

const appRoute = getRouteApi('/_app')

export function useAssistantSearch() {
  const search = appRoute.useSearch()
  const navigate = useNavigate()

  const patchSearch = (patch: (prev: MetricsSearch) => MetricsSearch) => {
    void navigate({ to: '/import-assistant', search: patch })
  }

  return {
    fileId: search.file_id,
    proposalId: search.proposal_id,
    dataSourceId: search.data_source_id,
    setFileId: (fileId: number | undefined) => {
      patchSearch((prev) => {
        const next: MetricsSearch = { ...prev }
        delete next.proposal_id
        if (fileId == null) delete next.file_id
        else next.file_id = fileId
        return next
      })
    },
    setProposalId: (proposalId: number | undefined) => {
      patchSearch((prev) => {
        const next: MetricsSearch = { ...prev }
        if (proposalId == null) delete next.proposal_id
        else next.proposal_id = proposalId
        return next
      })
    },
  }
}
