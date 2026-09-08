import { Bell } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { SearchField } from '@/components/ui/SearchField'

export function TopNav() {
  return (
    <header className="flex h-[var(--header-height)] items-center gap-3 px-4 md:px-8">
      <SearchField placeholder="Search sessions, imports, mappings…" aria-label="Global search" />
      <button
        type="button"
        className="hidden h-9 shrink-0 rounded-md border border-border bg-glass-soft px-3 text-secondary text-foreground-muted md:block"
      >
        All datasets
      </button>
      <button
        type="button"
        className="hidden h-9 shrink-0 rounded-md border border-border bg-glass-soft px-3 text-secondary text-foreground-muted lg:block"
      >
        Last 7 days
      </button>
      <Button variant="ghost" size="icon" aria-label="Notifications">
        <Bell />
      </Button>
      <div className="flex size-9 items-center justify-center rounded-full bg-primary-soft text-meta text-foreground">
        AS
      </div>
    </header>
  )
}
