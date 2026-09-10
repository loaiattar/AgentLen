import { useCallback, useMemo, useState } from 'react'

import {
  useCreateImportMutation,
  usePreviewImportMutation,
  useProfileFileMutation,
  useUploadFileMutation,
} from '@/features/imports/api/imports.queries'
import type { FileProfile, FileUpload, ImportPreview } from '@/features/imports/types'

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

interface WizardState {
  file: FileUpload | null
  profile: FileProfile | null
  dataSourceId: number | null
  mappingId: number | null
  preview: ImportPreview | null
  importRunId: number | null
  /** `already_seen` is a warning, not a block — but it must be acknowledged. */
  duplicateAcknowledged: boolean
}

const EMPTY_STATE: WizardState = {
  file: null,
  profile: null,
  dataSourceId: null,
  mappingId: null,
  preview: null,
  importRunId: null,
  duplicateAcknowledged: false,
}

/**
 * Drives `upload → profile → mapping → preview → import → tracking`.
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
  const [state, setState] = useState<WizardState>(EMPTY_STATE)
  const [sampleSize, setSampleSize] = useState(DEFAULT_SAMPLE_SIZE)

  const uploadMutation = useUploadFileMutation()
  const profileMutation = useProfileFileMutation()
  const previewMutation = usePreviewImportMutation()
  const createMutation = useCreateImportMutation()

  const reset = useCallback(() => {
    setState(EMPTY_STATE)
    uploadMutation.reset()
    profileMutation.reset()
    previewMutation.reset()
    createMutation.reset()
  }, [uploadMutation, profileMutation, previewMutation, createMutation])

  const uploadFile = useCallback(
    async (file: File) => {
      // A new file invalidates everything downstream of it.
      setState(EMPTY_STATE)
      previewMutation.reset()
      createMutation.reset()

      const upload = await uploadMutation.mutateAsync(file)
      setState((current) => ({ ...current, file: upload }))

      // Profiling is what makes the mapping step meaningful, so it runs
      // straight away; a failure here leaves the file selected and is
      // surfaced through `profileMutation.error` rather than thrown away.
      try {
        const profile = await profileMutation.mutateAsync(upload.id)
        setState((current) => ({ ...current, profile }))
      } catch {
        /* surfaced via profileMutation.error */
      }

      return upload
    },
    [uploadMutation, profileMutation, previewMutation, createMutation],
  )

  const retryProfile = useCallback(async () => {
    if (state.file === null) return
    const profile = await profileMutation.mutateAsync(state.file.id)
    setState((current) => ({ ...current, profile }))
  }, [state.file, profileMutation])

  const selectDataSource = useCallback((dataSourceId: number | null) => {
    setState((current) => ({
      ...current,
      dataSourceId,
      // Mappings are scoped to a source: keep no selection across a change.
      mappingId: null,
      preview: null,
    }))
    previewMutation.reset()
  }, [previewMutation])

  const selectMapping = useCallback((mappingId: number | null) => {
    setState((current) => ({ ...current, mappingId, preview: null }))
    previewMutation.reset()
  }, [previewMutation])

  const acknowledgeDuplicate = useCallback(() => {
    setState((current) => ({ ...current, duplicateAcknowledged: true }))
  }, [])

  const canPreview = state.file !== null && state.mappingId !== null

  const runPreview = useCallback(async () => {
    if (state.file === null || state.mappingId === null) return
    const preview = await previewMutation.mutateAsync({
      file_id: state.file.id,
      mapping_id: state.mappingId,
      sample_size: sampleSize,
    })
    setState((current) => ({ ...current, preview }))
  }, [state.file, state.mappingId, sampleSize, previewMutation])

  const duplicateBlocked = state.file?.already_seen === true && !state.duplicateAcknowledged

  const canLaunch =
    state.file !== null &&
    state.mappingId !== null &&
    state.dataSourceId !== null &&
    state.preview !== null &&
    !duplicateBlocked

  const launchBlockedReason = useMemo(() => {
    if (state.file === null) return 'Upload a file first.'
    if (state.dataSourceId === null) return 'Pick the data source this file belongs to.'
    if (state.mappingId === null) return 'Pick the mapping to apply.'
    if (state.preview === null) return 'Run the preview before importing.'
    if (duplicateBlocked) return 'This exact file was already imported — acknowledge before re-importing.'
    return null
  }, [state.file, state.dataSourceId, state.mappingId, state.preview, duplicateBlocked])

  const launchImport = useCallback(async () => {
    if (state.file === null || state.mappingId === null || state.dataSourceId === null) return
    // Belt and braces: the button is disabled, but the guard lives here too.
    if (state.preview === null) return

    const created = await createMutation.mutateAsync({
      data_source_id: state.dataSourceId,
      file_upload_id: state.file.id,
      mapping_id: state.mappingId,
    })
    setState((current) => ({ ...current, importRunId: created.import_run_id }))
    return created
  }, [state.file, state.mappingId, state.dataSourceId, state.preview, createMutation])

  const currentStep: WizardStep = useMemo(() => {
    if (state.importRunId !== null) return 'run'
    if (state.preview !== null) return 'preview'
    if (state.mappingId !== null) return 'mapping'
    if (state.profile !== null) return 'profile'
    if (state.file !== null) return 'profile'
    return 'upload'
  }, [state])

  return {
    ...state,
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
    profileMutation,
    previewMutation,
    createMutation,
  }
}
