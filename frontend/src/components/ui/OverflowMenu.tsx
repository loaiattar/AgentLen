import { DropdownMenu } from 'radix-ui'
import { MoreHorizontal } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'
import { Button } from '@/components/ui/Button'

export interface OverflowMenuItem {
  label: string
  onSelect?: () => void
  tone?: 'default' | 'danger'
  disabled?: boolean
}

export interface OverflowMenuProps {
  label?: string
  items: OverflowMenuItem[]
  trigger?: ReactNode
}

export function OverflowMenu({ label = 'More actions', items, trigger }: OverflowMenuProps) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        {trigger ?? (
          <Button variant="ghost" size="icon" aria-label={label}>
            <MoreHorizontal />
          </Button>
        )}
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className={cn(
            'z-50 min-w-44 overflow-hidden rounded-lg border border-glass-border bg-glass-strong p-1 shadow-pop backdrop-blur-[var(--glass-blur)]',
          )}
        >
          {items.map((item) => (
            <DropdownMenu.Item
              key={item.label}
              disabled={item.disabled}
              onSelect={item.onSelect}
              className={cn(
                'flex cursor-pointer items-center rounded-md px-2.5 py-2 text-secondary outline-none',
                'text-foreground data-[highlighted]:bg-primary-soft',
                'data-[disabled]:pointer-events-none data-[disabled]:opacity-40',
                item.tone === 'danger' && 'text-error data-[highlighted]:bg-error-soft',
              )}
            >
              {item.label}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
