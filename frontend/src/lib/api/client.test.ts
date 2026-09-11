import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '@/lib/api/client'

function answer(body: unknown, headers: Record<string, string> = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status: 200, headers })),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiClient.getWithTotal', () => {
  it('reads X-Total-Count next to the body', async () => {
    answer([{ id: 1 }], { 'X-Total-Count': '250' })

    await expect(apiClient.getWithTotal('/data-sources')).resolves.toEqual({ data: [{ id: 1 }], total: 250 })
  })

  it.each([
    ['absent', {}],
    ['not a count', { 'X-Total-Count': 'many' }],
    ['negative', { 'X-Total-Count': '-3' }],
  ])('reports an unknown total, not 0, when the header is %s', async (_, headers) => {
    answer([], headers)

    await expect(apiClient.getWithTotal('/data-sources')).resolves.toEqual({ data: [], total: null })
  })

  it('leaves get returning the bare body', async () => {
    answer([{ id: 1 }], { 'X-Total-Count': '250' })

    await expect(apiClient.get('/data-sources')).resolves.toEqual([{ id: 1 }])
  })
})
