import { getRouteApi, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import {
  DRILL_DOWN_KEYS,
  EXPLORATION_KEYS,
  readDateRange,
  searchToDashboardFilters,
  SESSION_PAGE_SIZE,
  withoutIgnoredDates,
  withoutSearchKeys,
  type MetricsSearch,
  type SessionStatus,
} from '@/features/dashboard/lib/filters'

const appRoute = getRouteApi('/_app')

export function useSessionsSearch() {
  const search = appRoute.useSearch()
  const navigate = useNavigate()
  const filters = searchToDashboardFilters(search)
  const limit = search.limit ?? SESSION_PAGE_SIZE
  const offset = search.offset ?? 0

  const patchSearch = (patch: (prev: MetricsSearch) => MetricsSearch) => {
    void navigate({ to: '/sessions', search: patch })
  }

  return {
    search,
    filters,
    limit,
    offset,
    // Every filter narrows the list, the header's dataset and period included.
    hasActiveFilters: Object.keys(filters).length > 0,
    // Dates stay raw in `search` (see `parseMetricsSearch`), so the page can say what it ignores.
    ignoredDates: readDateRange(search).ignored,
    setStatus: (status: SessionStatus | undefined) => {
      patchSearch((prev) => {
        const next = withoutSearchKeys(prev, ['status'])
        return status == null ? next : { ...next, status }
      })
    },
    clearKey: (key: (typeof DRILL_DOWN_KEYS)[number]) => patchSearch((prev) => withoutSearchKeys(prev, [key])),
    clearFilters: () =>
      patchSearch((prev) => withoutSearchKeys(prev, [...EXPLORATION_KEYS, 'period', 'data_source_id'])),
    dropIgnoredDates: () => patchSearch(withoutIgnoredDates),
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
