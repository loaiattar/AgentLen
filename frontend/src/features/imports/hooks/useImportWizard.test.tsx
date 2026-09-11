import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createTestQueryClient, withQueryClient } from '@/test/query'

const get = vi.fn()
const post = vi.fn()

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => get(...args),
    post: (...args: unknown[]) => post(...args),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

/**
 * The pipeline ids live in the router search, so the hook is driven through a
 * stand-in that behaves the same way: setters write, reads come back on the
 * next render. Mocking the router itself would test TanStack, not the wizard.
 */
const pipeline = {
  fileId: undefined as number | undefined,
  dataSourceId: undefined as number | undefined,
  mappingId: undefined as number | undefined,
  setFileId: vi.fn(),
  setDataSourceId: vi.fn(),
  setMappingId: vi.fn(),
  setProposalId: vi.fn(),
}

vi.mock('@/features/imports/hooks/usePipelineSearch', () => ({
  usePipelineSearch: () => pipeline,
}))

const { useImportWizard, clampSampleSize, MAX_SAMPLE_SIZE, MIN_SAMPLE_SIZE } = await import(
  '@/features/imports/hooks/useImportWizard'
)

const FILE = {
  id: 7,
  original_name: 'trace.jsonl',
  format: 'jsonl',
  size_bytes: 2048,
  content_hash: 'a'.repeat(64),
  already_seen: false,
  previous_import_run_ids: [] as number[],
}

const PREVIEW = {
  entities: [{ target: 'session', rows: [{ external_id: 'a' }] }],
  counts: { session: 1 },
  issues: [],
}

const PROFILE = { file_id: 7, format: 'jsonl', record_count: 1, sampled_records: 1, fields: [] }

/**
 * `POST` serves four routes here — the upload, profiling, the dry run and the
 * launch — so the double dispatches on the path. Queuing responses in call
 * order made the profile query, which fires on mount, eat the one meant for the
 * preview.
 */
function routePost(overrides: Record<string, unknown> = {}) {
  const answer = (value: unknown) =>
    value instanceof Error ? Promise.reject(value) : Promise.resolve(value)

  post.mockImplementation((url: string) => {
    if (url.includes('/profile')) return answer(overrides.profile ?? PROFILE)
    if (url.includes('/imports/preview')) return answer(overrides.preview ?? PREVIEW)
    if (url.startsWith('/files')) return answer(overrides.upload ?? FILE)
    return answer(overrides.create ?? { import_run_id: 42 })
  })
}

function importCalls() {
  return post.mock.calls.filter(
    ([url]) => typeof url === 'string' && url.includes('/imports') && !url.includes('/preview'),
  )
}

function render() {
  return renderHook(() => useImportWizard(), { wrapper: withQueryClient(createTestQueryClient()) })
}

beforeEach(() => {
  get.mockReset()
  post.mockReset()
  pipeline.fileId = undefined
  pipeline.dataSourceId = undefined
  pipeline.mappingId = undefined
  pipeline.setFileId.mockReset()
  pipeline.setDataSourceId.mockReset()
  pipeline.setMappingId.mockReset()
  get.mockResolvedValue(FILE)
  routePost()
})

describe('clampSampleSize', () => {
  it('bounds both ends — the server has no upper limit of its own', () => {
    expect(clampSampleSize(9999999)).toBe(MAX_SAMPLE_SIZE)
    expect(clampSampleSize(0)).toBe(MIN_SAMPLE_SIZE)
    expect(clampSampleSize(-5)).toBe(MIN_SAMPLE_SIZE)
    expect(clampSampleSize(50)).toBe(50)
  })

  it('falls back to the default on a value that is not a number', () => {
    // `Number('')` is 0 and `Number('abc')` is NaN; neither should become 1 and
    // silently preview a single record.
    expect(clampSampleSize(Number.NaN)).toBe(20)
    expect(clampSampleSize(Number.POSITIVE_INFINITY)).toBe(20)
  })

  it('truncates rather than rounding — a fractional sample size is nonsense', () => {
    expect(clampSampleSize(20.9)).toBe(20)
  })
})

describe('the steps', () => {
  it('starts at upload with nothing selected', () => {
    const { result } = render()

    expect(result.current.currentStep).toBe('upload')
    expect(result.current.canPreview).toBe(false)
    expect(result.current.canLaunch).toBe(false)
  })

  it('reaches mapping once a file and a mapping are chosen', async () => {
    pipeline.fileId = 7
    pipeline.mappingId = 3
    const { result } = render()

    await waitFor(() => expect(result.current.file).not.toBeNull())
    expect(result.current.currentStep).toBe('mapping')
    expect(result.current.canPreview).toBe(true)
  })

  it('reaches preview only after the dry run has actually returned', async () => {
    pipeline.fileId = 7
    pipeline.mappingId = 3
    const { result } = render()
    await waitFor(() => expect(result.current.file).not.toBeNull())

    await act(async () => {
      await result.current.runPreview()
    })

    expect(result.current.preview).not.toBeNull()
    expect(result.current.currentStep).toBe('preview')
  })
})

describe('the launch preconditions', () => {
  it('names the first thing missing, in the order the user must supply it', async () => {
    const { result } = render()
    expect(result.current.launchBlockedReason).toBe('Upload a file first.')

    pipeline.fileId = 7
    const withFile = render()
    await waitFor(() => expect(withFile.result.current.file).not.toBeNull())
    expect(withFile.result.current.launchBlockedReason).toBe(
      'Pick the data source this file belongs to.',
    )

    pipeline.dataSourceId = 2
    const withSource = render()
    await waitFor(() => expect(withSource.result.current.file).not.toBeNull())
    expect(withSource.result.current.launchBlockedReason).toBe('Pick the mapping to apply.')

    pipeline.mappingId = 3
    const withMapping = render()
    await waitFor(() => expect(withMapping.result.current.file).not.toBeNull())
    expect(withMapping.result.current.launchBlockedReason).toBe(
      'Run the preview before importing.',
    )
  })

  it('refuses to launch without a preview, even if called directly', async () => {
    pipeline.fileId = 7
    pipeline.dataSourceId = 2
    pipeline.mappingId = 3
    const { result } = render()
    await waitFor(() => expect(result.current.file).not.toBeNull())

    await act(async () => {
      await result.current.launchImport()
    })

    expect(importCalls()).toHaveLength(0)
    expect(result.current.importRunId).toBeNull()
  })

  it('launches once every precondition is met', async () => {
    pipeline.fileId = 7
    pipeline.dataSourceId = 2
    pipeline.mappingId = 3
    const { result } = render()
    await waitFor(() => expect(result.current.file).not.toBeNull())

    await act(async () => {
      await result.current.runPreview()
    })
    expect(result.current.canLaunch).toBe(true)
    await act(async () => {
      await result.current.launchImport()
    })

    expect(result.current.importRunId).toBe(42)
    expect(result.current.currentStep).toBe('run')
  })
})

describe('the duplicate gate', () => {
  it('does not block a file that was uploaded but never imported', async () => {
    // The bug this pins: `already_seen` is true as soon as the *content hash*
    // is known, so "Replace" followed by re-picking the same file warned that
    // it "has already been imported" about an import that never happened.
    get.mockResolvedValue({ ...FILE, already_seen: true, previous_import_run_ids: [] })
    pipeline.fileId = 7
    pipeline.dataSourceId = 2
    pipeline.mappingId = 3
    const { result } = render()

    await waitFor(() => expect(result.current.file).not.toBeNull())

    expect(result.current.duplicateBlocked).toBe(false)
  })

  it('blocks a file a past run actually imported, until it is acknowledged', async () => {
    get.mockResolvedValue({ ...FILE, already_seen: true, previous_import_run_ids: [11] })
    pipeline.fileId = 7
    pipeline.dataSourceId = 2
    pipeline.mappingId = 3
    const { result } = render()
    await waitFor(() => expect(result.current.file).not.toBeNull())
    await act(async () => {
      await result.current.runPreview()
    })

    expect(result.current.duplicateBlocked).toBe(true)
    expect(result.current.canLaunch).toBe(false)
    expect(result.current.launchBlockedReason).toContain('already imported')

    act(() => {
      result.current.acknowledgeDuplicate()
    })

    expect(result.current.duplicateBlocked).toBe(false)
    expect(result.current.canLaunch).toBe(true)
  })
})

describe('the preview is never stale', () => {
  it('discards it when the mapping changes', async () => {
    pipeline.fileId = 7
    pipeline.mappingId = 3
    const { result, rerender } = render()
    await waitFor(() => expect(result.current.file).not.toBeNull())
    await act(async () => {
      await result.current.runPreview()
    })
    expect(result.current.preview).not.toBeNull()

    pipeline.mappingId = 4
    rerender()

    expect(result.current.preview).toBeNull()
    expect(result.current.canLaunch).toBe(false)
  })

  it('discards it, and the acknowledgement, when the file changes', async () => {
    get.mockResolvedValue({ ...FILE, already_seen: true, previous_import_run_ids: [11] })
    pipeline.fileId = 7
    pipeline.mappingId = 3
    const { result, rerender } = render()
    await waitFor(() => expect(result.current.file).not.toBeNull())
    await act(async () => {
      await result.current.runPreview()
    })
    act(() => {
      result.current.acknowledgeDuplicate()
    })
    expect(result.current.duplicateAcknowledged).toBe(true)

    pipeline.fileId = 8
    rerender()

    expect(result.current.preview).toBeNull()
    expect(result.current.duplicateAcknowledged).toBe(false)
  })
})

describe('failures surface without becoming unhandled rejections', () => {
  it('an upload that fails leaves the wizard on the upload step', async () => {
    routePost({ upload: new Error('413 Payload Too Large') })
    const { result } = render()

    let returned: unknown = 'untouched'
    await act(async () => {
      returned = await result.current.uploadFile(new File(['{}'], 'trace.jsonl'))
    })

    expect(returned).toBeUndefined()
    expect(pipeline.setFileId).not.toHaveBeenCalled()
    await waitFor(() => expect(result.current.uploadMutation.isError).toBe(true))
  })

  it('a preview that fails leaves the previous state alone', async () => {
    pipeline.fileId = 7
    pipeline.mappingId = 3
    routePost({ preview: new Error('422') })
    const { result } = render()
    await waitFor(() => expect(result.current.file).not.toBeNull())

    await act(async () => {
      await result.current.runPreview()
    })

    expect(result.current.preview).toBeNull()
    expect(result.current.canLaunch).toBe(false)
    await waitFor(() => expect(result.current.previewMutation.isError).toBe(true))
  })
})
