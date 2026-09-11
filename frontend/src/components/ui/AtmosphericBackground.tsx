import { cn } from '@/lib/utils/cn'

export interface AtmosphericBackgroundProps {
  className?: string
}

export function AtmosphericBackground({ className }: AtmosphericBackgroundProps) {
  return (
    <div
      aria-hidden
      className={cn('atmosphere atmosphere-motion pointer-events-none fixed inset-0 -z-10', className)}
    />
  )
}
