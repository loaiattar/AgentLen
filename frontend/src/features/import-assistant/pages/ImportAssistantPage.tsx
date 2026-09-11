import type { FormEvent } from 'react'
import { useEffect } from 'react'
import { Link } from '@tanstack/react-router'

import { AiPanel } from '@/components/ui/AiPanel'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { PageHeader } from '@/components/ui/PageHeader'
import { GlassSkeleton } from '@/components/ui/Skeleton'
import { Textarea } from '@/components/ui/Textarea'
import {
  usePatchProposalMutation,
  useProposeMappingMutation,
  useRefineProposalMutation,
} from '@/features/import-assistant/api/assistant.mutations'
import { useProposalQuery } from '@/features/import-assistant/api/assistant.queries'
import { DatasetColumn } from '@/features/import-assistant/components/DatasetColumn'
import { FilePicker } from '@/features/import-assistant/components/FilePicker'
import { MappingColumn } from '@/features/import-assistant/components/MappingColumn'
import { useAssistantSearch } from '@/features/import-assistant/hooks/useAssistantSearch'
import { proposalInsights } from '@/features/import-assistant/lib/insights'
import { describeProposalChange, updateFieldSource } from '@/features/import-assistant/lib/mapping'
import { useImportAssistantStore } from '@/features/import-assistant/store/import-assistant.store'
import { useFileProfileQuery, useFileQuery, usePreviewImportMutation } from '@/features/imports/api/imports.queries'
import { PreviewPanel } from '@/features/imports/components/PreviewPanel'
import { useCreateMappingMutation } from '@/features/mappings/api/mappings.queries'
// The shell asks for `/ai/providers` too: one query key, one request.
import { useAiProvidersQuery } from '@/features/system/api/system.queries'

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

export function ImportAssistantPage() {
  const { fileId, proposalId, mappingId, dataSourceId, setFileId, setProposalId, setMappingId } =
    useAssistantSearch()
  const syncProposal = useImportAssistantStore((state) => state.syncProposal)
  const composer = useImportAssistantStore((state) => state.composer)
  const turns = useImportAssistantStore((state) => state.turns)
  const mappingDraft = useImportAssistantStore((state) => state.mappingDraft)
  const acceptedMappingId = useImportAssistantStore((state) => state.acceptedMappingId)
  const setComposer = useImportAssistantStore((state) => state.setComposer)
  const pushTurn = useImportAssistantStore((state) => state.pushTurn)
  const setMappingDraft = useImportAssistantStore((state) => state.setMappingDraft)
  const clearMappingDraft = useImportAssistantStore((state) => state.clearMappingDraft)
  const setAcceptedMappingId = useImportAssistantStore((state) => state.setAcceptedMappingId)

  useEffect(() => {
    syncProposal(proposalId, mappingId)
  }, [proposalId, mappingId, syncProposal])

  const providers = useAiProvidersQuery()
  const file = useFileQuery(fileId)
  const profile = useFileProfileQuery(fileId)
  const proposal = useProposalQuery(proposalId)

  const propose = useProposeMappingMutation()
  const refine = useRefineProposalMutation()
  const patch = usePatchProposalMutation()
  const accept = useCreateMappingMutation()
  const preview = usePreviewImportMutation()

  const mapping = mappingDraft ?? proposal.data?.mapping
  const activeProvider = providers.data?.active
  const canPropose = fileId != null && !propose.isPending
  // Refining asks the server to rework *its* proposal, which knows nothing of an
  // unsaved draft. Save the edits first rather than let the round-trip drop them.
  const canRefine =
    proposalId != null && proposal.data != null && mappingDraft == null && acceptedMappingId == null
  const canAccept =
    proposal.data != null &&
    proposal.data.validation.valid &&
    dataSourceId != null &&
    mapping != null &&
    mappingDraft == null &&
    acceptedMappingId == null &&
    !accept.isPending

  const askAssistant = () => {
    if (fileId == null) return
    propose.mutate(
      {
        file_id: fileId,
        data_source_id: dataSourceId,
        provider: null,
        model: null,
      },
      {
        onSuccess: (data) => setProposalId(data.proposal_id),
      },
    )
  }

  const saveEdits = () => {
    if (proposalId == null || mappingDraft == null) return
    patch.mutate({ proposalId, mapping: mappingDraft }, { onSuccess: () => clearMappingDraft() })
  }

  const sendMessage = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const message = composer.trim()
    if (!message || !canRefine || refine.isPending) return
    const previous = proposal.data
    if (previous == null) return
    refine.mutate(
      { proposalId, message },
      {
        onSuccess: (next) => {
          pushTurn({ role: 'user', content: message })
          pushTurn({ role: 'status', content: describeProposalChange(previous, next) })
          setComposer('')
        },
      },
    )
  }

  const acceptMapping = () => {
    if (mapping == null || dataSourceId == null || proposalId == null) return
    accept.mutate(
      {
        data_source_id: dataSourceId,
        name: `${mapping.name || 'mapping'}-p${proposalId}`,
        source_format: mapping.source_format,
        entities: mapping.entities,
      },
      {
        onSuccess: (saved) => {
          setAcceptedMappingId(saved.id)
          setMappingId(saved.id)
        },
      },
    )
  }

  const runPreview = () => {
    if (fileId == null || acceptedMappingId == null) return
    preview.mutate({ file_id: fileId, mapping_id: acceptedMappingId, sample_size: 20 })
  }

  const continueImport = (
    <Button asChild>
      <Link to="/imports/new" search={(prev) => prev}>
        Continue import
      </Link>
    </Button>
  )

  const headerAction = (() => {
    if (fileId == null) return null
    if (proposalId == null) {
      return (
        <Button type="button" onClick={askAssistant} loading={propose.isPending} disabled={!canPropose}>
          Propose mapping
        </Button>
      )
    }
    if (acceptedMappingId != null) {
      return (
        <div className="flex flex-wrap items-center gap-2">
          {continueImport}
          <Button type="button" variant="secondary" onClick={runPreview} loading={preview.isPending}>
            Preview
          </Button>
        </div>
      )
    }
    return (
      <Button type="button" onClick={acceptMapping} disabled={!canAccept} loading={accept.isPending}>
        Accept mapping
      </Button>
    )
  })()

  return (
    <div>
      <PageHeader title="Mapping studio" action={headerAction} />

      <FilePicker key={fileId ?? 'none'} fileId={fileId} fileName={file.data?.original_name} onSubmit={setFileId} />
      {fileId != null ? (
        <p className="mb-[var(--space-3)] text-secondary">
          <Link
            to="/imports/new"
            search={(prev) => prev}
            className="text-primary underline-offset-4 hover:underline"
          >
            Back to import
          </Link>
        </p>
      ) : null}

      {providers.isError ? (
        <p role="status" className="mb-[var(--space-3)] text-body text-error">
          {errorMessage(providers.error, 'Unable to load AI providers.')}
        </p>
      ) : activeProvider ? (
        <p className="mb-[var(--space-3)] text-secondary text-foreground-muted">
          Server analyzer · {activeProvider.provider}
          {activeProvider.model ? ` · ${activeProvider.model}` : ''}
        </p>
      ) : null}

      {fileId == null ? (
        <EmptyState
          title="Select a file"
          description="Open this studio from New import, or enter an already uploaded file id. The seed TraceLab sample is 1."
        />
      ) : file.isError || profile.isError ? (
        <EmptyState
          title="File unavailable"
          description={errorMessage(file.error ?? profile.error, 'Unable to load this file profile.')}
        />
      ) : file.isPending || profile.isPending ? (
        <div className="grid gap-bento xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,0.9fr)]">
          <GlassSkeleton className="min-h-72" />
          <GlassSkeleton className="min-h-72" />
          <GlassSkeleton className="min-h-72" />
        </div>
      ) : profile.data == null ? (
        <EmptyState title="No profile" description="This file could not be profiled." />
      ) : (
        <div className="grid gap-bento xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,0.9fr)]">
          <DatasetColumn
            profile={profile.data}
            alreadyImported={(file.data?.previous_import_run_ids.length ?? 0) > 0}
          />

          {proposalId == null ? (
            <section className="glass-module order-1 flex min-h-72 flex-col justify-between p-6 xl:order-2">
              <div>
                <h2 className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">
                  Mapping
                </h2>
                <p className="mt-4 text-body text-foreground-muted">
                  No proposal yet. Ask the assistant to map this profile.
                </p>
              </div>
            </section>
          ) : proposal.isPending ? (
            <GlassSkeleton className="order-1 min-h-72 xl:order-2" />
          ) : proposal.isError ? (
            <EmptyState
              title="Proposal unavailable"
              description={errorMessage(proposal.error, 'Unable to load this proposal.')}
              action={
                <Button variant="secondary" onClick={() => void proposal.refetch()}>
                  Retry
                </Button>
              }
            />
          ) : mapping ? (
            <MappingColumn
              mapping={mapping}
              rationale={proposal.data?.rationale ?? []}
              dirty={mappingDraft != null}
              saving={patch.isPending}
              locked={acceptedMappingId != null || refine.isPending}
              onSaveEdits={saveEdits}
              onSourceChange={(entity, target, source) => {
                if (proposalId == null || acceptedMappingId != null || refine.isPending) return
                setMappingDraft(proposalId, updateFieldSource(mapping, entity, target, source))
              }}
            />
          ) : (
            <EmptyState title="Empty mapping" description="The proposal has no mapping document." />
          )}

          <AiPanel
            className="order-2 xl:order-3"
            insights={
              proposal.data
                ? proposalInsights(proposal.data)
                : [
                    {
                      title: 'Ready when you are',
                      body: 'The assistant never runs in the browser. Propose a mapping from the profile, then you validate.',
                    },
                  ]
            }
            footer={
              <div className="grid gap-3">
                {turns.length > 0 ? (
                  <ul className="grid max-h-40 gap-2 overflow-auto">
                    {turns.map((turn, index) => (
                      <li key={`${turn.role}-${index}`} className="text-secondary text-foreground-muted">
                        <span className="text-meta uppercase text-foreground-subtle">{turn.role} · </span>
                        {turn.content}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {propose.isError ? (
                  <p role="alert" className="text-secondary text-error">
                    {errorMessage(propose.error, 'The assistant could not propose a mapping.')}
                  </p>
                ) : null}
                {refine.isError ? (
                  <p role="alert" className="text-secondary text-error">
                    {errorMessage(refine.error, 'The assistant could not refine this mapping.')}
                  </p>
                ) : null}
                {patch.isError ? (
                  <p role="alert" className="text-secondary text-error">
                    {errorMessage(patch.error, 'Edits could not be saved.')}
                  </p>
                ) : null}
                {accept.isError ? (
                  <p role="alert" className="text-secondary text-error">
                    {errorMessage(accept.error, 'The mapping could not be saved.')}
                  </p>
                ) : null}
                {acceptedMappingId != null ? (
                  <p className="text-secondary text-foreground-muted">
                    Saved as mapping {acceptedMappingId}. Continue the import to preview and launch.
                  </p>
                ) : mappingDraft != null ? (
                  <p className="text-secondary text-foreground-muted">
                    Save your edits before accepting or refining. The assistant does not apply a mapping on
                    its own.
                  </p>
                ) : dataSourceId == null && proposal.data != null ? (
                  <p className="text-secondary text-foreground-muted">
                    Pick a data source in the import wizard or the top bar before accepting.
                  </p>
                ) : null}
                <form onSubmit={sendMessage} className="grid gap-2">
                  <Textarea
                    value={composer}
                    disabled={!canRefine || refine.isPending}
                    placeholder={
                      acceptedMappingId != null
                        ? 'Mapping already accepted'
                        : proposalId == null
                          ? 'Propose a mapping first'
                          : mappingDraft != null
                            ? 'Save your edits first'
                            : 'Ask the assistant to adjust a field'
                    }
                    aria-label="Message to the mapping assistant"
                    onChange={(event) => setComposer(event.target.value)}
                  />
                  <Button
                    type="submit"
                    variant="ai"
                    size="sm"
                    disabled={!canRefine || composer.trim().length === 0}
                    loading={refine.isPending}
                  >
                    Send
                  </Button>
                </form>
              </div>
            }
          />
        </div>
      )}

      {preview.isError ? (
        <p role="alert" className="mt-[var(--space-3)] text-body text-error">
          {errorMessage(preview.error, 'Preview failed.')}
        </p>
      ) : null}

      {preview.data ? <PreviewPanel preview={preview.data} /> : null}
    </div>
  )
}
