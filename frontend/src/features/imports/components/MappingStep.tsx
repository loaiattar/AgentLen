import { Link } from '@tanstack/react-router'

import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Select } from '@/features/imports/components/SelectField'
import { useDataSourcesQuery } from '@/features/imports/api/imports.queries'
import { useMappingsQuery } from '@/features/mappings/api/mappings.queries'

export interface MappingStepProps {
  fileId: number | null
  dataSourceId: number | null
  mappingId: number | null
  onDataSourceChange: (id: number | null) => void
  onMappingChange: (id: number | null) => void
}

/**
 * Picks the data source the file belongs to and the mapping to apply.
 *
 * The select only *chooses* among saved mappings; authoring one is the
 * assistant's job (#31), so the hint links there carrying this file and source
 * — the assistant needs a `file_id` to propose anything, and this wizard is
 * where a file exists. Coming back, a mapping saved through
 * `useCreateMappingMutation` lands in the list below on its own: both features
 * invalidate the same `mappingKeys`.
 *
 * `GET /mappings` can still be missing on an older deployment, so the select
 * degrades to a plain id input when the route answers an error rather than a
 * list. That keeps the import path usable — the seeded `tracelab-jsonl`
 * mapping has an id the user can read off `make seed`.
 */
export function MappingStep({
  fileId,
  dataSourceId,
  mappingId,
  onDataSourceChange,
  onMappingChange,
}: MappingStepProps) {
  const dataSources = useDataSourcesQuery()
  const mappings = useMappingsQuery(dataSourceId ?? undefined)

  const mappingsUnavailable = mappings.isError

  const assistantLink =
    fileId === null ? null : (
      <Link
        to="/import-assistant"
        search={(prev) => ({
          ...prev,
          file_id: fileId,
          data_source_id: dataSourceId ?? undefined,
        })}
        className="text-primary underline-offset-2 hover:underline"
      >
        Let the assistant propose one
      </Link>
    )

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Field
        label="Data source"
        htmlFor="import-data-source"
        hint={
          dataSources.isError
            ? undefined
            : 'Where these traces come from — kept with the import for provenance.'
        }
        error={dataSources.isError ? dataSources.error.message : undefined}
      >
        <Select
          id="import-data-source"
          value={dataSourceId ?? ''}
          disabled={dataSources.isPending || dataSources.isError}
          error={dataSources.isError}
          onChange={(event) =>
            onDataSourceChange(event.target.value === '' ? null : Number(event.target.value))
          }
        >
          <option value="">
            {dataSources.isPending ? 'Loading…' : 'Select a data source'}
          </option>
          {(dataSources.data ?? []).map((source) => (
            <option key={source.id} value={source.id}>
              {source.name} ({source.slug})
            </option>
          ))}
        </Select>
      </Field>

      {mappingsUnavailable ? (
        <Field
          label="Mapping id"
          htmlFor="import-mapping-id"
          hint={
            <>
              GET /mappings is unavailable on this backend. Enter the mapping id directly.
              {assistantLink === null ? null : <> Or: {assistantLink}.</>}
            </>
          }
        >
          <Input
            id="import-mapping-id"
            type="number"
            min={1}
            inputMode="numeric"
            placeholder="e.g. 1"
            value={mappingId ?? ''}
            onChange={(event) =>
              onMappingChange(event.target.value === '' ? null : Number(event.target.value))
            }
          />
        </Field>
      ) : (
        <Field
          label="Mapping"
          htmlFor="import-mapping"
          hint={
            <>
              The document that turns this file&rsquo;s fields into the common model.
              {assistantLink === null ? null : <> No mapping fits? {assistantLink}.</>}
            </>
          }
        >
          <Select
            id="import-mapping"
            value={mappingId ?? ''}
            disabled={mappings.isPending}
            onChange={(event) =>
              onMappingChange(event.target.value === '' ? null : Number(event.target.value))
            }
          >
            <option value="">{mappings.isPending ? 'Loading…' : 'Select a mapping'}</option>
            {(mappings.data ?? []).map((mapping) => (
              <option key={mapping.id} value={mapping.id}>
                {mapping.name} · v{mapping.version} ({mapping.status})
              </option>
            ))}
          </Select>
        </Field>
      )}
    </div>
  )
}
