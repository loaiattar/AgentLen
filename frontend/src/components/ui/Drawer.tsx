import { Dialog } from 'radix-ui'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils/cn'

export interface DrawerProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
}

export function Drawer({ open, onOpenChange, title, description, children, footer }: DrawerProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-overlay backdrop-blur-sm" />
        <Dialog.Content
          className={cn(
            'glass-surface fixed inset-y-0 right-0 z-50 flex w-[min(28rem,100vw)] flex-col border-y-0 border-r-0 p-6 shadow-pop',
          )}
        >
          <Dialog.Title className="font-display text-section text-foreground">{title}</Dialog.Title>
          {description ? (
            <Dialog.Description className="mt-2 text-body text-foreground-muted">{description}</Dialog.Description>
          ) : null}
          <div className="mt-6 flex-1 overflow-y-auto">{children}</div>
          {footer ? <div className="mt-6 flex justify-end gap-2">{footer}</div> : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
