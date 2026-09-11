/** `GET /ai/providers` — `provider_status()` in `infrastructure/ai/factory.py`. Never carries a key. */
export interface AiProvidersResponse {
  active: {
    provider: string
    /** `null` when the server has no model configured for the active provider. */
    model: string | null
  }
  available: { provider: string; configured: boolean }[]
}

export type ReadinessCheckStatus = 'ok' | 'error' | 'stale' | 'unknown'

/** `GET /health/ready` — answered with HTTP 503 and `status: "not_ready"` when a dependency fails. */
export interface ReadinessResponse {
  status: 'ready' | 'not_ready'
  checks: Record<string, { status: ReadinessCheckStatus; detail: string | null }>
}
