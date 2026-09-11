import { getRouteApi, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import {
  searchToDashboardFilters,
  SESSION_PAGE_SIZE,
  type MetricsSearch,
  type SessionStatus,
} from '@/features/dashboard/lib/filters'

const appRoute = getRouteApi('/_app')

const DRILL_DOWN_KEYS = ['agent_id', 'model_id', 'tool_id', 'import_run_id', 'date_from', 'date_to'] as const

export function useSessionsSearch() {
  const search = appRoute.useSearch()
  const navigate = useNavigate()
  const filters = searchToDashboardFilters(search)
  const limit = search.limit ?? SESSION_PAGE_SIZE
  const offset = search.offset ?? 0

  const patchSearch = (patch: (prev: MetricsSearch) => MetricsSearch) => {
    void navigate({ to: '/sessions', search: patch })
  }

  const resetOffset = (next: MetricsSearch): MetricsSearch => {
    const copy = { ...next }
    delete copy.offset
    return copy
  }

  return {
    search,
    filters,
    limit,
    offset,
    setStatus: (status: SessionStatus | undefined) => {
      patchSearch((prev) => {
        const next: MetricsSearch = { ...prev }
        if (status == null) delete next.status
        else next.status = status
        return resetOffset(next)
      })
    },
    clearKey: (key: (typeof DRILL_DOWN_KEYS)[number]) => {
      patchSearch((prev) => {
        const next: MetricsSearch = { ...prev }
        delete next[key]
        if (key === 'date_from' || key === 'date_to') delete next.period
        return resetOffset(next)
      })
    },
    clearExploration: () => {
      patchSearch((prev) => {
        const next: MetricsSearch = { ...prev }
        delete next.agent_id
        delete next.model_id
        delete next.tool_id
        delete next.import_run_id
        delete next.date_from
        delete next.date_to
        delete next.status
        delete next.period
        return resetOffset(next)
      })
    },
    setOffset: (nextOffset: number) => {
      patchSearch((prev) => {
        const next: MetricsSearch = { ...prev }
        if (nextOffset <= 0) delete next.offset
        else next.offset = nextOffset
        return next
      })
    },
    openSession: (sessionId: number | string) => {
      void navigate({
        to: '/sessions/$sessionId',
        params: { sessionId: String(sessionId) },
        search: (prev) => prev,
      })
    },
    drillDownKeys: DRILL_DOWN_KEYS,
  }
}

export function useSessionIdSearch() {
  const navigate = useNavigate()
  const [value, setValue] = useState('')

  const submit = () => {
    const id = value.trim()
    if (!/^\d+$/.test(id)) return
    void navigate({
      to: '/sessions/$sessionId',
      params: { sessionId: id },
      search: (prev) => prev,
    })
  }

  return { value, setValue, submit }
}
