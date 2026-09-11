import { cva } from 'class-variance-authority'
import {
  Activity,
  Database,
  FolderInput,
  GitBranch,
  LayoutGrid,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'

export interface ShellNavItem {
  to: '/overview' | '/sessions' | '/imports' | '/sources' | '/mappings' | '/quality'
  label: string
  icon: LucideIcon
}

export const SHELL_NAV_ITEMS: readonly ShellNavItem[] = [
  { to: '/overview', label: 'Overview', icon: LayoutGrid },
  { to: '/sessions', label: 'Sessions', icon: Activity },
  { to: '/imports', label: 'Imports', icon: FolderInput },
  { to: '/sources', label: 'Data Sources', icon: Database },
  { to: '/mappings', label: 'Mappings', icon: GitBranch },
  { to: '/quality', label: 'Data Quality', icon: ShieldCheck },
] as const

export const MOBILE_PRIMARY_NAV = SHELL_NAV_ITEMS.filter((item) =>
  item.to === '/overview' || item.to === '/sessions' || item.to === '/imports' || item.to === '/quality',
)

export const MOBILE_MORE_NAV = SHELL_NAV_ITEMS.filter(
  (item) => item.to === '/sources' || item.to === '/mappings',
)

export function isShellNavActive(pathname: string, to: ShellNavItem['to']) {
  if (to === '/overview') return pathname === '/overview' || pathname === '/overview/'
  return pathname === to || pathname.startsWith(`${to}/`)
}

export const shellNavItemVariants = cva(
  [
    'relative outline-none',
    'transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out)]',
    'motion-reduce:transition-none',
    'focus-visible:ring-2 focus-visible:ring-primary-emphasis focus-visible:ring-offset-2 focus-visible:ring-offset-background',
    'active:opacity-80',
  ],
  {
    variants: {
      layout: {
        sidebar: 'flex items-center gap-[var(--space-1)] rounded-md px-[var(--space-2)] py-[var(--space-1)] text-body',
        mobile:
          'flex flex-col items-center justify-center gap-[var(--space-1)] rounded-md px-[var(--space-1)] py-[var(--space-1)] text-meta',
      },
      active: {
        true: 'bg-primary-soft text-foreground',
        false: 'text-foreground-muted hover:bg-primary-soft hover:text-foreground',
      },
    },
    defaultVariants: {
      layout: 'sidebar',
      active: false,
    },
  },
)
