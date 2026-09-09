import { Bell } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { SearchField } from '@/components/ui/SearchField'

export function TopNav() {
  return (
    <header className="flex h-[var(--header-height)] items-center gap-[var(--space-1)] px-[var(--space-2)] md:px-[var(--space-4)]">
      <SearchField placeholder="Search sessions, imports, mappings…" aria-label="Global search" />

      <Button type="button" variant="secondary" size="sm" className="hidden shrink-0 md:inline-flex">
        All datasets
      </Button>
      <Button type="button" variant="secondary" size="sm" className="hidden shrink-0 lg:inline-flex">
        Last 7 days
      </Button>

      <Button type="button" variant="ghost" size="icon" aria-label="Notifications">
        <Bell />
      </Button>

      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Account"
        className="rounded-pill bg-primary-soft text-meta text-foreground"
      >
        AS
      </Button>
    </header>
  )
}
