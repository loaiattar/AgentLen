import { clearSessionToken, getSessionToken } from '@/lib/auth/session'

/** Backend prefix from API.md. Paths passed to apiClient are relative to this (e.g. `/metrics/overview`). */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
const API_KEY = import.meta.env.VITE_API_KEY ?? ''

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

async function request<TResponse>(path: string, options: RequestOptions = {}): Promise<TResponse> {
  const { body, headers, ...rest } = options
  const isFormData = body instanceof FormData
  const sessionToken = getSessionToken()

  const response = await fetch(joinUrl(API_BASE_URL, path), {
    ...rest,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
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
    return undefined as TResponse
  }

  return (await response.json()) as TResponse
}

export const apiClient = {
  get: <TResponse>(path: string, options?: RequestOptions) =>
    request<TResponse>(path, { ...options, method: 'GET' }),
  post: <TResponse>(path: string, body?: unknown, options?: RequestOptions) =>
    request<TResponse>(path, { ...options, method: 'POST', body }),
  patch: <TResponse>(path: string, body?: unknown, options?: RequestOptions) =>
    request<TResponse>(path, { ...options, method: 'PATCH', body }),
  put: <TResponse>(path: string, body?: unknown, options?: RequestOptions) =>
    request<TResponse>(path, { ...options, method: 'PUT', body }),
  delete: <TResponse>(path: string, options?: RequestOptions) =>
    request<TResponse>(path, { ...options, method: 'DELETE' }),
}
