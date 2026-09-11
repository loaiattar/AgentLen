import { useState } from 'react'

import { Link, useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { PageHeader } from '@/components/ui/PageHeader'
import { GlassSkeleton } from '@/components/ui/Skeleton'
import { FileDropzone } from '@/features/imports/components/FileDropzone'
import { FileSummary } from '@/features/imports/components/FileSummary'
import { ImportReportCard } from '@/features/imports/components/ImportReportCard'
import { IssuesTable } from '@/features/imports/components/IssuesTable'
import { MappingStep } from '@/features/imports/components/MappingStep'
import { PreviewPanel } from '@/features/imports/components/PreviewPanel'
import { ProfileTable } from '@/features/imports/components/ProfileTable'
import { WizardSteps } from '@/features/imports/components/WizardSteps'
import { useImportQuery, useImportIssuesQuery } from '@/features/imports/api/imports.queries'
import {
  MAX_SAMPLE_SIZE,
  MIN_SAMPLE_SIZE,
  useImportWizard,
} from '@/features/imports/hooks/useImportWizard'
import { isTerminal } from '@/features/imports/types'

function Section({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <section className="mt-10">
      <h2 className="font-display text-section text-foreground">{title}</h2>
      {description ? (
        <p className="mt-1 max-w-2xl text-body text-foreground-muted">{description}</p>
      ) : null}
      <div className="mt-6">{children}</div>
    </section>
  )
}

function ErrorNote({ error }: { error: Error | null }) {
  if (!error) return null
  return (
    <p role="alert" className="mt-3 text-secondary text-error">
      {error.message}
    </p>
  )
}

/**
 * `upload → profile → mapping → preview → import → tracking` (issue #30).
 *
 * The launch button stays disabled until a preview has been run against the
 * current file and mapping; `useImportWizard` discards the preview whenever
 * either changes, so what the user validated is always what gets imported.
 */
export function ImportWizardPage() {
  const navigate = useNavigate()
  const wizard = useImportWizard()
  const [sampleSizeDraft, setSampleSizeDraft] = useState(String(wizard.sampleSize))

  // Starts as soon as the run exists and stops on its own at a terminal status.
  const run = useImportQuery(wizard.importRunId)
  // The run's status is handed to the issues query so it polls on the same
  // terms. Without it the first and only request went out while the run was
  // still `pending` and had no issue yet, and the cached empty page was what
  // the report below rendered once the run ended `partial`.
  const issues = useImportIssuesQuery(wizard.importRunId, undefined, { limit: 20 }, run.data?.status)

  const runFinished = run.data !== undefined && isTerminal(run.data.status)

  return (
    <div>
      <PageHeader
        title="New import"
        action={
          <Button variant="secondary" asChild>
            <Link to="/imports" search={(prev) => prev}>
              Import history
            </Link>
          </Button>
        }
      />

      <WizardSteps current={wizard.currentStep} />

      {wizard.fileQuery.isLoading ? (
        <GlassSkeleton className="h-40" />
      ) : wizard.file === null ? (
        <FileDropzone
          onFileSelected={(file) => {
            void wizard.uploadFile(file)
          }}
          busy={wizard.uploadMutation.isPending}
          // `busy` only puts the button in a loading state; the drop handler and
          // the hidden input stay live. Dropping a second file mid-upload ran
          // two uploads whose results raced, and the slower one won.
          disabled={wizard.uploadMutation.isPending}
        />
      ) : (
        <FileSummary
          file={wizard.file}
          profile={wizard.profile}
          acknowledged={wizard.duplicateAcknowledged}
          onAcknowledge={wizard.acknowledgeDuplicate}
          onReplace={wizard.reset}
        />
      )}
      <ErrorNote error={wizard.uploadMutation.error ?? wizard.fileQuery.error} />

      {wizard.file !== null ? (
        <Section
          title="Field profile"
          description="Types, null ratio and cardinality, computed by the backend on a bounded sample."
        >
          {wizard.profileQuery.isLoading ? (
            <GlassSkeleton className="h-48" />
          ) : wizard.profile !== null ? (
            <ProfileTable profile={wizard.profile} />
          ) : (
            <div className="glass-surface rounded-xl p-6">
              <p className="text-body text-foreground">This file could not be profiled.</p>
              <ErrorNote error={wizard.profileQuery.error} />
              <Button
                variant="secondary"
                size="sm"
                className="mt-4"
                loading={wizard.profileQuery.isFetching}
                onClick={() => {
                  void wizard.retryProfile()
                }}
              >
                Retry profiling
              </Button>
            </div>
          )}
        </Section>
      ) : null}

      {wizard.file !== null ? (
        <Section
          title="Source and mapping"
          description="The mapping turns this file's fields into the common model. No code is executed."
        >
          <MappingStep
            fileId={wizard.file.id}
            dataSourceId={wizard.dataSourceId}
            mappingId={wizard.mappingId}
            onDataSourceChange={wizard.selectDataSource}
            onMappingChange={wizard.selectMapping}
          />

          <div className="mt-6 flex flex-wrap items-end gap-4">
            <Field label="Sample size" htmlFor="preview-sample-size" className="w-40">
              <Input
                id="preview-sample-size"
                type="number"
                min={MIN_SAMPLE_SIZE}
                max={MAX_SAMPLE_SIZE}
                value={sampleSizeDraft}
                onChange={(event) => {
                  // The draft is what the field shows, so it can be cleared
                  // while typing. `Number('') || 1` used to snap an emptied
                  // field to 1, which turned a retyped "5" into 15.
                  const raw = event.target.value
                  setSampleSizeDraft(raw)
                  if (raw === '') return
                  wizard.setSampleSize(Number(raw))
                }}
                onBlur={() => setSampleSizeDraft(String(wizard.sampleSize))}
              />
            </Field>
            <Button
              disabled={!wizard.canPreview}
              loading={wizard.previewMutation.isPending}
              onClick={() => {
                void wizard.runPreview()
              }}
            >
              Run preview
            </Button>
            {!wizard.canPreview ? (
              <p className="text-secondary text-foreground-subtle">
                Pick a mapping to enable the preview.
              </p>
            ) : null}
          </div>
          <ErrorNote error={wizard.previewMutation.error} />
        </Section>
      ) : null}

      {wizard.preview !== null ? (
        <Section
          title="Preview"
          description="A dry run over the sample. Nothing is written until you launch the import."
        >
          <PreviewPanel preview={wizard.preview} />

          {wizard.importRunId === null ? (
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Button
                disabled={!wizard.canLaunch}
                loading={wizard.createMutation.isPending}
                onClick={() => {
                  void wizard.launchImport()
                }}
              >
                Launch import
              </Button>
              {wizard.launchBlockedReason ? (
                <p className="text-secondary text-foreground-subtle">
                  {wizard.launchBlockedReason}
                </p>
              ) : null}
            </div>
          ) : null}
          <ErrorNote error={wizard.createMutation.error} />
        </Section>
      ) : null}

      {wizard.importRunId !== null ? (
        <Section
          title="Import"
          description="The worker claims the run and reports progress. This page polls until it settles."
        >
          {run.isPending ? (
            <GlassSkeleton className="h-40" />
          ) : run.isError ? (
            <ErrorNote error={run.error} />
          ) : run.data ? (
            <>
              <ImportReportCard run={run.data} />

              {runFinished && (run.data.report.records_rejected > 0 ||
                run.data.report.records_duplicate > 0) ? (
                <div className="mt-8">
                  <h3 className="mb-4 text-card text-foreground">Issues</h3>
                  <IssuesTable
                    issues={issues.data?.items ?? []}
                    total={issues.data?.total}
                    severity="all"
                    filterable={false}
                    emptyMessage={
                      issues.isPending ? 'Loading issues…' : 'No issue recorded for this run.'
                    }
                  />
                </div>
              ) : null}

              <div className="mt-8 flex flex-wrap gap-3">
                <Button
                  variant="secondary"
                  onClick={() =>
                    void navigate({
                      to: '/imports/$importId',
                      params: { importId: String(wizard.importRunId) },
                    })
                  }
                >
                  Open full report
                </Button>
                <Button variant="ghost" onClick={wizard.reset}>
                  Import another file
                </Button>
              </div>
            </>
          ) : null}
        </Section>
      ) : null}
    </div>
  )
}
