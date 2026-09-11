import { cva } from 'class-variance-authority'

/**
 * The variant table, out of the component file so fast refresh keeps working.
 *
 * `react(only-export-components)`: a module that exports a component *and*
 * something else cannot be hot-replaced, so every edit to Button.tsx forced a
 * full page reload — on one of the most-edited files in the project. Same
 * separation as `shell-nav.ts`.
 */
export const buttonVariants = cva(
  "relative inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-body font-medium transition-[transform,background,border,box-shadow,opacity] duration-[var(--duration-fast)] ease-[var(--ease-out)] outline-none focus-visible:ring-2 focus-visible:ring-primary-emphasis/80 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-40 aria-disabled:pointer-events-none aria-disabled:opacity-40 data-[loading=true]:pointer-events-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        primary:
          'bg-primary text-on-dark shadow-glass hover:brightness-[1.08] active:scale-[0.98] active:brightness-[0.94]',
        secondary:
          'glass-surface text-foreground hover:bg-glass-strong hover:border-glass-border-strong active:scale-[0.98]',
        ghost:
          'bg-transparent text-foreground hover:bg-primary-soft hover:text-foreground active:scale-[0.98]',
        text: 'bg-transparent px-0 text-foreground underline-offset-4 hover:underline active:opacity-80',
        ai: 'bg-accent-magenta-soft text-foreground ring-1 ring-accent-magenta/25 hover:ring-accent-magenta/45 active:scale-[0.98]',
        danger:
          'bg-error-soft text-foreground ring-1 ring-error/30 hover:bg-error/20 active:scale-[0.98]',
      },
      size: {
        sm: 'h-8 px-3 text-secondary',
        default: 'h-9 px-4',
        lg: 'h-11 px-5 text-card',
        icon: 'size-9',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'default',
    },
  },
)
