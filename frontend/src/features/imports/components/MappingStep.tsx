import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Select } from '@/features/imports/components/SelectField'
import { useDataSourcesQuery, useMappingsQuery } from '@/features/imports/api/imports.queries'

export interface MappingStepProps {
  dataSourceId: number | null
  mappingId: number | null
  onDataSourceChange: (id: number | null) => void
  onMappingChange: (id: number | null) => void
}

/**
 * Picks the data source the file belongs to and the mapping to apply.
 *
 * `GET /mappings` (API.md §4) is owned by issue #52 and is not merged yet, so
 * the select degrades to a plain id input when the route answers an error
 * instead of a list. That keeps the whole import path usable today — the seeded
 * `tracelab-jsonl` mapping has an id the user can read off `make seed` — and
 * needs no change here once #52 lands.
 */
export function MappingStep({
  dataSourceId,
  mappingId,
  onDataSourceChange,
  onMappingChange,
}: MappingStepProps) {
  const dataSources = useDataSourcesQuery()
  const mappings = useMappingsQuery(dataSourceId ?? undefined)

  const mappingsUnavailable = mappings.isError

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
          hint="GET /mappings is unavailable on this backend (issue #52). Enter the mapping id directly."
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
          hint="The document that turns this file's fields into the common model."
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
