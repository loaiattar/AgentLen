import { Search, X } from 'lucide-react'

import { Button } from '@/components/atoms/Button'
import { Input, type InputProps } from '@/components/atoms/Input'
import { cn } from '@/lib/utils/cn'

export interface SearchInputProps extends Omit<InputProps, 'value' | 'onChange' | 'type'> {
  value: string
  onChange: (value: string) => void
}

export function SearchInput({ value, onChange, className, ...props }: SearchInputProps) {
  return (
    <div className={cn('relative flex items-center', className)}>
      <Search className="pointer-events-none absolute left-2.5 size-4 text-muted-foreground" />
      <Input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="pl-8 pr-8"
        {...props}
      />
      {value.length > 0 && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="absolute right-0.5 size-7"
          onClick={() => onChange('')}
        >
          <X className="size-3.5" />
          <span className="sr-only">Effacer la recherche</span>
        </Button>
      )}
    </div>
  )
}
