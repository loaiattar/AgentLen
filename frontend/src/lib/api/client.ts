import { clearSessionToken, getSessionToken } from '@/lib/auth/session'

/** Backend prefix from API.md. Paths passed to apiClient are relative to this (e.g. `/metrics/overview`). */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
// No `X-API-Key` here: anything this code can read ships in the bundle. The
// proxy in front of the API (nginx in Docker, Vite in dev) adds it (#149).

export class ApiError extends Error {
  status: number
  code: string | null
  body: unknown

  constructor(message: string, status: number, body: unknown, code: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.body = body
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
}

function joinUrl(base: string, path: string): string {
  const normalizedBase = base.replace(/\/$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${normalizedBase}${normalizedPath}`
}

function errorPayload(body: unknown): { message?: unknown; code?: unknown } | undefined {
  if (body && typeof body === 'object' && 'error' in body) {
    return (body as { error?: { message?: unknown; code?: unknown } }).error
  }
  return undefined
}

function messageFromErrorBody(body: unknown, fallback: string): string {
  const payload = errorPayload(body)
  if (typeof payload?.message === 'string' && payload.message.length > 0) {
    return payload.message
  }
  return fallback
}

function codeFromErrorBody(body: unknown): string | null {
  const payload = errorPayload(body)
  if (typeof payload?.code === 'string' && payload.code.length > 0) {
    return payload.code
  }
  return null
}

/** Name of the count header sent by the bounded bare-array routes (API.md §1). */
export const TOTAL_COUNT_HEADER = 'X-Total-Count'

/** A response body with the row count its route reported, `null` when it reported none. */
export interface WithTotal<TResponse> {
  data: TResponse
  total: number | null
}

/** An absent or malformed header is an unknown total, never `0`. */
export function parseTotalCount(headers: Headers): number | null {
  const raw = headers.get(TOTAL_COUNT_HEADER)
  if (raw === null || !/^\d+$/.test(raw.trim())) return null
  return Number(raw)
}

async function send<TResponse>(
  path: string,
  options: RequestOptions = {},
): Promise<{ data: TResponse; headers: Headers }> {
  const { body, headers, ...rest } = options
  const isFormData = body instanceof FormData
  const sessionToken = getSessionToken()

  const response = await fetch(joinUrl(API_BASE_URL, path), {
    ...rest,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(sessionToken ? { Authorization: `Bearer ${sessionToken}` } : {}),
      ...headers,
    },
    body: isFormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
    credentials: 'include',
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null)
    const code = codeFromErrorBody(errorBody)
    if (code === 'UNAUTHENTICATED') {
      clearSessionToken()
    }
    throw new ApiError(messageFromErrorBody(errorBody, response.statusText), response.status, errorBody, code)
  }

  if (response.status === 204) {
    return { data: undefined as TResponse, headers: response.headers }
  }

  return { data: (await response.json()) as TResponse, headers: response.headers }
}

async function request<TResponse>(path: string, options: RequestOptions = {}): Promise<TResponse> {
  return (await send<TResponse>(path, options)).data
}

export const apiClient = {
  get: <TResponse>(path: string, options?: RequestOptions) =>
    request<TResponse>(path, { ...options, method: 'GET' }),
  /** `get`, plus `X-Total-Count`: how a bounded bare array tells it was cut short. */
  getWithTotal: async <TResponse>(path: string, options?: RequestOptions): Promise<WithTotal<TResponse>> => {
    const { data, headers } = await send<TResponse>(path, { ...options, method: 'GET' })
    return { data, total: parseTotalCount(headers) }
  },
  post: <TResponse>(path: string, body?: unknown, options?: RequestOptions) =>
    request<TResponse>(path, { ...options, method: 'POST', body }),
  patch: <TResponse>(path: string, body?: unknown, options?: RequestOptions) =>
    request<TResponse>(path, { ...options, method: 'PATCH', body }),
  put: <TResponse>(path: string, body?: unknown, options?: RequestOptions) =>
    request<TResponse>(path, { ...options, method: 'PUT', body }),
  delete: <TResponse>(path: string, options?: RequestOptions) =>
    request<TResponse>(path, { ...options, method: 'DELETE' }),
}
