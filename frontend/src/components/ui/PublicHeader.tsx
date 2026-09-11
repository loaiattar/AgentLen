import type { ReactNode } from 'react'
import { Link } from '@tanstack/react-router'

import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { Wordmark } from '@/components/ui/Wordmark'
import { cn } from '@/lib/utils/cn'

export interface PublicHeaderProps {
  trailing?: ReactNode
  className?: string
}

export function PublicHeader({ trailing, className }: PublicHeaderProps) {
  return (
    <header
      className={cn(
        'flex h-[var(--header-height)] items-center justify-between px-[var(--space-2)] md:px-[var(--space-4)]',
        className,
      )}
    >
      <Link
        to="/"
        className="outline-none focus-visible:ring-2 focus-visible:ring-primary-emphasis focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      >
        <Wordmark />
      </Link>
      <div className="flex items-center gap-[var(--space-1)]">
        <ThemeToggle />
        {trailing}
      </div>
    </header>
  )
}
