import type { FileProfile } from '@/features/import-assistant/types'

export interface DatasetColumnProps {
  profile: FileProfile
  alreadySeen?: boolean
}

export function DatasetColumn({ profile, alreadySeen = false }: DatasetColumnProps) {
  return (
    <section className="glass-module order-3 p-6 xl:order-1">
      <h2 className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">Dataset</h2>
      <p className="mt-2 text-secondary text-foreground-muted">
        {profile.record_count} records · {profile.sampled_records} sampled
      </p>
      {alreadySeen ? (
        <p className="mt-2 text-secondary text-foreground-muted">
          This content was already stored. Review before importing.
        </p>
      ) : null}
      {profile.fields.length === 0 ? (
        <p className="mt-6 text-body text-foreground-muted">No fields in this profile.</p>
      ) : (
        <ul className="mt-6 grid gap-5">
          {profile.fields.map((field) => (
            <li key={field.path}>
              <p className="text-card text-foreground">{field.path}</p>
              <p className="text-secondary text-foreground-muted">
                {field.types.join(', ') || '—'}
                {field.examples[0] ? ` · ${field.examples[0]}` : ''}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
