import { Check } from 'lucide-react'

import { cn } from '@/lib/utils/cn'
import { STEP_LABELS, WIZARD_STEPS, type WizardStep } from '@/features/imports/hooks/useImportWizard'

export interface WizardStepsProps {
  current: WizardStep
}

export function WizardSteps({ current }: WizardStepsProps) {
  const currentIndex = WIZARD_STEPS.indexOf(current)

  return (
    <ol className="glass-surface mb-8 flex flex-wrap items-center gap-x-2 gap-y-3 rounded-xl px-4 py-3">
      {WIZARD_STEPS.map((step, index) => {
        const done = index < currentIndex
        const active = index === currentIndex

        return (
          <li key={step} className="flex items-center gap-2">
            <span
              aria-hidden
              className={cn(
                'flex size-6 items-center justify-center rounded-full text-meta font-medium transition-colors',
                done && 'bg-success-soft text-foreground',
                active && 'bg-primary-emphasis text-foreground',
                !done && !active && 'bg-surface-sunken text-foreground-subtle',
              )}
            >
              {done ? <Check className="size-3.5" /> : index + 1}
            </span>
            <span
              aria-current={active ? 'step' : undefined}
              className={cn(
                'text-secondary',
                active ? 'text-foreground' : 'text-foreground-muted',
              )}
            >
              {STEP_LABELS[step]}
            </span>
            {index < WIZARD_STEPS.length - 1 ? (
              <span aria-hidden className="ml-1 h-px w-6 bg-border md:w-10" />
            ) : null}
          </li>
        )
      })}
    </ol>
  )
}
