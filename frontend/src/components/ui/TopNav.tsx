import { Bell, ChevronDown } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { OverflowMenu, type OverflowMenuItem } from '@/components/ui/OverflowMenu'
import { SearchField } from '@/components/ui/SearchField'

export interface TopNavProps {
  datasetLabel: string
  periodLabel: string
  datasetItems: OverflowMenuItem[]
  periodItems: OverflowMenuItem[]
  accountLabel?: string
  accountItems?: OverflowMenuItem[]
}

export function TopNav({
  datasetLabel,
  periodLabel,
  datasetItems,
  periodItems,
  accountLabel = 'AS',
  accountItems,
}: TopNavProps) {
  return (
    <header className="flex h-[var(--header-height)] items-center gap-[var(--space-1)] px-[var(--space-2)] md:px-[var(--space-4)]">
      <SearchField placeholder="Search sessions, imports, mappings…" aria-label="Global search" />

      <OverflowMenu
        label="Dataset"
        items={datasetItems}
        trigger={
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="shrink-0 bg-primary-soft text-foreground ring-1 ring-border hover:bg-primary-soft hover:text-foreground hover:ring-border-strong"
          >
            {datasetLabel}
            <ChevronDown />
          </Button>
        }
      />
      <OverflowMenu
        label="Period"
        items={periodItems}
        trigger={
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="shrink-0 bg-primary-soft text-foreground ring-1 ring-border hover:bg-primary-soft hover:text-foreground hover:ring-border-strong"
          >
            {periodLabel}
            <ChevronDown />
          </Button>
        }
      />

      <Button type="button" variant="ghost" size="icon" aria-label="Notifications">
        <Bell />
      </Button>

      {accountItems && accountItems.length > 0 ? (
        <OverflowMenu
          label="Account"
          items={accountItems}
          trigger={
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Account"
              className="rounded-pill bg-primary-soft text-meta text-foreground"
            >
              {accountLabel}
            </Button>
          }
        />
      ) : (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Account"
          className="rounded-pill bg-primary-soft text-meta text-foreground"
        >
          {accountLabel}
        </Button>
      )}
    </header>
  )
}
