import { cn } from '@/lib/utils/cn'

export interface WordmarkProps {
  className?: string
}

export function Wordmark({ className }: WordmarkProps) {
  return <span className={cn('font-display text-section text-foreground', className)}>AgentScope</span>
}
