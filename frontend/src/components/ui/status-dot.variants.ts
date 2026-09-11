import { cva } from 'class-variance-authority'

/**
 * The variant table, out of the component file so fast refresh keeps working.
 *
 * `react(only-export-components)`: a module that exports a component *and*
 * something else cannot be hot-replaced, so every edit to StatusDot.tsx forced a
 * full page reload — on one of the most-edited files in the project. Same
 * separation as `shell-nav.ts`.
 */
export const statusDotVariants = cva('inline-block size-1.5 shrink-0 rounded-full', {
  variants: {
    tone: {
      live: 'bg-primary-emphasis shadow-[0_0_8px_var(--color-primary-emphasis)]',
      success: 'bg-success',
      warning: 'bg-warning',
      error: 'bg-error',
      muted: 'bg-foreground-subtle',
      ai: 'bg-accent-magenta',
    },
  },
  defaultVariants: {
    tone: 'muted',
  },
})
