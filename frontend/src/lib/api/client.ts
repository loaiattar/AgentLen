/** Backend prefix from API.md. Paths passed to apiClient are relative to this (e.g. `/metrics/overview`). */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(message: string, status: number, body: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
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

async function request<TResponse>(path: string, options: RequestOptions = {}): Promise<TResponse> {
  const { body, headers, ...rest } = options
  const isFormData = body instanceof FormData

  const response = await fetch(joinUrl(API_BASE_URL, path), {
    ...rest,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...headers,
    },
    body: isFormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
    credentials: 'include',
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null)
    throw new ApiError(response.statusText, response.status, errorBody)
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
