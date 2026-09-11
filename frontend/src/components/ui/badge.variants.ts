import { cva } from 'class-variance-authority'

/**
 * The variant table, out of the component file so fast refresh keeps working.
 *
 * `react(only-export-components)`: a module that exports a component *and*
 * something else cannot be hot-replaced, so every edit to Badge.tsx forced a
 * full page reload — on one of the most-edited files in the project. Same
 * separation as `shell-nav.ts`.
 */
export const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-pill px-2.5 py-0.5 text-meta font-medium tracking-wide',
  {
    variants: {
      tone: {
        neutral: 'bg-surface-sunken text-foreground-muted',
        cyan: 'bg-primary-soft text-foreground',
        mint: 'bg-success-soft text-foreground',
        magenta: 'bg-accent-magenta-soft text-foreground',
        pink: 'bg-error-soft text-foreground',
        blue: 'bg-info-soft text-foreground',
        warning: 'bg-warning-soft text-foreground',
      },
    },
    defaultVariants: {
      tone: 'neutral',
    },
  },
)
