import * as React from 'react'

import { Label } from '@/components/atoms/Label'
import { cn } from '@/lib/utils/cn'

export interface FormFieldProps {
  label: string
  htmlFor: string
  error?: string
  children: React.ReactNode
  className?: string
}

export function FormField({ label, htmlFor, error, children, className }: FormFieldProps) {
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
