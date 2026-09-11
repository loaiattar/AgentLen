import type { AppSidebarDetail, AppSidebarStatus } from '@/components/ui/AppSidebar'
import type { AiProvidersResponse, ReadinessResponse } from '@/features/system/types'

/** The subset of a TanStack Query result these helpers read. */
export interface QueryState<T> {
  status: 'pending' | 'error' | 'success'
  data: T | undefined
  error: unknown
}

const MISSING = '—'

function placeholders(value: string): AppSidebarDetail[] {
  return [
    { label: 'Provider', value, muted: true },
    { label: 'Model', value, muted: true },
  ]
}

/**
 * Active provider and model as reported by the server. Nothing is guessed: while
 * loading or on error the rows say so, and a model the server does not report is a dash.
 */
export function providerDetails(query: QueryState<AiProvidersResponse>): AppSidebarDetail[] {
  if (query.status === 'pending') return placeholders('Loading…')
  // An error wins over data kept from an earlier success: stale values are not shown as current.
  if (query.status === 'error' || !query.data) return placeholders('Unavailable')

  const { provider, model } = query.data.active
  return [
    { label: 'Provider', value: provider || MISSING, muted: !provider },
    { label: 'Model', value: model || MISSING, muted: !model },
  ]
}

function httpStatus(error: unknown): number | null {
  if (error !== null && typeof error === 'object' && 'status' in error && typeof error.status === 'number') {
    return error.status
  }
  return null
}

/** API readiness from `GET /health/ready`; a failed request is "unavailable", never "ready". */
export function readinessStatus(query: QueryState<ReadinessResponse>): AppSidebarStatus {
  if (query.status === 'pending') return { tone: 'muted', label: 'Checking API…' }
  if (query.status === 'success' && query.data?.status === 'ready') {
    return { tone: 'success', label: 'API ready' }
  }
  // The endpoint answers 503 with `not_ready` when the database or the schema is not usable.
  if (query.status === 'success' || httpStatus(query.error) === 503) {
    return { tone: 'warning', label: 'API not ready' }
  }
  return { tone: 'error', label: 'Status unavailable' }
}
