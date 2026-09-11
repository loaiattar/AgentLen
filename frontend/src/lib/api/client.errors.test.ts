import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiClient } from '@/lib/api/client'

function answer(body: string, init: ResponseInit) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, init)))
}

async function failure(): Promise<ApiError> {
  const error: unknown = await apiClient.get('/metrics/overview').catch((caught: unknown) => caught)
  expect(error).toBeInstanceOf(ApiError)
  return error as ApiError
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ApiError message', () => {
  it('names the status when neither the body nor statusText gives a message', async () => {
    // A proxy's HTML 502, over HTTP/2: no JSON error, and `statusText` is empty.
    answer('<html>Bad Gateway</html>', { status: 502, statusText: '' })

    const error = await failure()

    expect(error.message).toBe('Request failed with status 502')
    expect(error.status).toBe(502)
  })

  it('uses statusText when there is one and the body has no message', async () => {
    answer('not json', { status: 503, statusText: 'Service Unavailable' })

    expect((await failure()).message).toBe('Service Unavailable')
  })

  it('prefers the API message and code', async () => {
    const body = { error: { code: 'NOT_FOUND', message: 'FileUpload 9 not found' } }
    answer(JSON.stringify(body), { status: 404, statusText: '' })

    const error = await failure()

    expect(error.message).toBe('FileUpload 9 not found')
    expect(error.code).toBe('NOT_FOUND')
  })
})
