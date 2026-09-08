import type { ComponentProps } from 'react'
import { Search } from 'lucide-react'

import { cn } from '@/lib/utils/cn'
import { Input } from '@/components/ui/Input'

export interface SearchFieldProps extends ComponentProps<'input'> {}

export function SearchField({ className, ...props }: SearchFieldProps) {
  return (
    <label className={cn('relative block min-w-0 flex-1', className)}>
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-foreground-subtle" />
      <Input className="h-9 bg-glass/80 pr-3 pl-9" {...props} />
    </label>
  )
}
