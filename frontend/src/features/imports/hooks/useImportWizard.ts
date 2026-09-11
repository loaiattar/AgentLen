import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  useCreateImportMutation,
  useFileProfileQuery,
  useFileQuery,
  usePreviewImportMutation,
  useUploadFileMutation,
} from '@/features/imports/api/imports.queries'
import { usePipelineSearch } from '@/features/imports/hooks/usePipelineSearch'
import type { ImportPreview } from '@/features/imports/types'

export const WIZARD_STEPS = ['upload', 'profile', 'mapping', 'preview', 'run'] as const
export type WizardStep = (typeof WIZARD_STEPS)[number]

export const STEP_LABELS: Record<WizardStep, string> = {
  upload: 'Upload',
  profile: 'Profile',
  mapping: 'Mapping',
  preview: 'Preview',
  run: 'Import',
}

const DEFAULT_SAMPLE_SIZE = 20

/**
 * The preview reads this many records server-side, and `ImportPreviewIn` bounds
 * it at `ge=1` with no upper limit — so the clamp has to happen here. `max` on a
 * number input is advisory: a typed value above it is accepted and submitted.
 */
export const MIN_SAMPLE_SIZE = 1
export const MAX_SAMPLE_SIZE = 500

export function clampSampleSize(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_SAMPLE_SIZE
  return Math.min(Math.max(Math.trunc(value), MIN_SAMPLE_SIZE), MAX_SAMPLE_SIZE)
}

/**
 * Drives `upload → profile → mapping → preview → import → tracking`.
 *
 * File, source and mapping live in the shared pipeline search so the mapping
 * studio can leave and come back without losing the run. Local state is only
 * what must not survive a mapping change: the dry-run, the duplicate ack, and
 * the launched run id.
 *
 * Two invariants the issue calls out explicitly, enforced here rather than in
 * the page so no future caller can route around them:
 *
 *  - the preview is a **precondition** of the launch, and any change to the
 *    file or the mapping discards it — a stale preview must never be what the
 *    user validated against;
 *  - a file the backend reports as `already_seen` needs an explicit
 *    acknowledgement before the import can start.
 */
export function useImportWizard() {
  const pipeline = usePipelineSearch('/imports/new')
  const fileId = pipeline.fileId ?? null
  const dataSourceId = pipeline.dataSourceId ?? null
  const mappingId = pipeline.mappingId ?? null

  const fileQuery = useFileQuery(fileId)
  const profileQuery = useFileProfileQuery(fileId)
  const file = fileQuery.data ?? null
  const profile = profileQuery.data ?? null

  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [importRunId, setImportRunId] = useState<number | null>(null)
  const [duplicateAcknowledged, setDuplicateAcknowledged] = useState(false)
  const [sampleSize, setRawSampleSize] = useState(DEFAULT_SAMPLE_SIZE)
  const setSampleSize = useCallback((value: number) => {
    setRawSampleSize(clampSampleSize(value))
  }, [])

  const uploadMutation = useUploadFileMutation()
  const previewMutation = usePreviewImportMutation()
  const createMutation = useCreateImportMutation()

  useEffect(() => {
    setPreview(null)
    setImportRunId(null)
    setDuplicateAcknowledged(false)
    previewMutation.reset()
    createMutation.reset()
  }, [fileId, previewMutation.reset, createMutation.reset])

  useEffect(() => {
    setPreview(null)
    previewMutation.reset()
  }, [mappingId, previewMutation.reset])

  const reset = useCallback(() => {
    pipeline.setFileId(undefined)
    setPreview(null)
    setImportRunId(null)
    setDuplicateAcknowledged(false)
    uploadMutation.reset()
    previewMutation.reset()
    createMutation.reset()
  }, [pipeline.setFileId, uploadMutation, previewMutation, createMutation])

  const uploadFile = useCallback(
    async (fileToUpload: File) => {
      previewMutation.reset()
      createMutation.reset()
      setPreview(null)
      setImportRunId(null)
      setDuplicateAcknowledged(false)

      let upload
      try {
        upload = await uploadMutation.mutateAsync(fileToUpload)
      } catch {
        return undefined
      }
      pipeline.setFileId(upload.id)
      return upload
    },
    [pipeline.setFileId, uploadMutation, previewMutation, createMutation],
  )

  const retryProfile = useCallback(async () => {
    if (fileId == null) return
    await profileQuery.refetch()
  }, [fileId, profileQuery])

  const selectDataSource = useCallback(
    (nextDataSourceId: number | null) => {
      pipeline.setDataSourceId(nextDataSourceId ?? undefined)
    },
    [pipeline.setDataSourceId],
  )

  const selectMapping = useCallback(
    (nextMappingId: number | null) => {
      pipeline.setMappingId(nextMappingId ?? undefined)
    },
    [pipeline.setMappingId],
  )

  const acknowledgeDuplicate = useCallback(() => {
    setDuplicateAcknowledged(true)
  }, [])

  const canPreview = file !== null && mappingId !== null

  const runPreview = useCallback(async () => {
    if (file === null || mappingId === null) return
    try {
      const nextPreview = await previewMutation.mutateAsync({
        file_id: file.id,
        mapping_id: mappingId,
        sample_size: sampleSize,
      })
      setPreview(nextPreview)
    } catch {
      /* surfaced via previewMutation.error */
    }
  }, [file, mappingId, sampleSize, previewMutation])

  // `already_seen` comes back true whenever the *content hash* is known, even
  // when the file was uploaded and never imported (`upload_file.py` returns the
  // existing row with `previous_import_run_ids: []`). Only a past run makes a
  // re-import a duplicate, so that is what gates the launch — otherwise
  // "Replace" followed by re-picking the same file blocked the wizard behind a
  // warning about an import that never happened.
  const alreadyImported = (file?.previous_import_run_ids?.length ?? 0) > 0
  const duplicateBlocked = alreadyImported && !duplicateAcknowledged

  const canLaunch =
    file !== null &&
    mappingId !== null &&
    dataSourceId !== null &&
    preview !== null &&
    !duplicateBlocked

  const launchBlockedReason = useMemo(() => {
    if (file === null) return 'Upload a file first.'
    if (dataSourceId === null) return 'Pick the data source this file belongs to.'
    if (mappingId === null) return 'Pick the mapping to apply.'
    if (preview === null) return 'Run the preview before importing.'
    if (duplicateBlocked) return 'This exact file was already imported — acknowledge before re-importing.'
    return null
  }, [file, dataSourceId, mappingId, preview, duplicateBlocked])

  const launchImport = useCallback(async () => {
    if (file === null || mappingId === null || dataSourceId === null) return
    if (preview === null) return

    let created
    try {
      created = await createMutation.mutateAsync({
        data_source_id: dataSourceId,
        file_upload_id: file.id,
        mapping_id: mappingId,
      })
    } catch {
      return undefined
    }
    setImportRunId(created.import_run_id)
    return created
  }, [file, mappingId, dataSourceId, preview, createMutation])

  const currentStep: WizardStep = useMemo(() => {
    if (importRunId !== null) return 'run'
    if (preview !== null) return 'preview'
    if (mappingId !== null) return 'mapping'
    if (profile !== null) return 'profile'
    if (file !== null) return 'profile'
    return 'upload'
  }, [importRunId, preview, mappingId, profile, file])

  return {
    file,
    profile,
    dataSourceId,
    mappingId,
    preview,
    importRunId,
    duplicateAcknowledged,
    fileQuery,
    profileQuery,
    sampleSize,
    setSampleSize,
    currentStep,
    canPreview,
    canLaunch,
    duplicateBlocked,
    launchBlockedReason,
    uploadFile,
    retryProfile,
    selectDataSource,
    selectMapping,
    acknowledgeDuplicate,
    runPreview,
    launchImport,
    reset,
    uploadMutation,
    previewMutation,
    createMutation,
  }
}
