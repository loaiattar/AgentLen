import { Link } from '@tanstack/react-router'

import { Wordmark } from '@/components/ui/Wordmark'

const links = [
  { href: 'https://github.com/loaiattar/AgentLen', label: 'GitHub' },
  {
    href: 'https://github.com/loaiattar/AgentLen/tree/main/docs/architecture',
    label: 'Architecture',
  },
] as const

export function LandingFooter() {
  return (
    <footer className="mt-[var(--space-6)] border-t border-border px-[var(--space-2)] py-[var(--space-4)] md:px-[var(--space-4)]">
      <div className="mx-auto flex max-w-7xl flex-col gap-[var(--space-3)] md:flex-row md:items-center md:justify-between">
        <Wordmark className="text-card" />
        <nav aria-label="Project" className="flex flex-wrap items-center gap-[var(--space-3)]">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-secondary text-foreground-muted outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary-emphasis"
            >
              {link.label}
            </a>
          ))}
          <Link
            to="/login"
            className="text-secondary text-foreground-muted outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary-emphasis"
          >
            Sign in
          </Link>
          <Link
            to="/register"
            className="text-secondary text-primary outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary-emphasis"
          >
            Get started
          </Link>
        </nav>
      </div>
    </footer>
  )
}
