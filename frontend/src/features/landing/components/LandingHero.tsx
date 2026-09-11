import { Link } from '@tanstack/react-router'

import { BentoGrid, BentoModule } from '@/components/ui/Bento'
import { Button } from '@/components/ui/Button'
import { DashboardPreview } from '@/features/landing/components/DashboardPreview'

export interface LandingHeroProps {
  authenticated: boolean
}

export function LandingHero({ authenticated }: LandingHeroProps) {
  return (
    <section className="grid gap-[var(--space-4)] pt-[var(--space-3)] md:pt-[var(--space-4)]">
      <div className="max-w-3xl" data-reveal="hero">
        <p className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">
          Observability
        </p>
        <h1 className="mt-[var(--space-2)] font-display text-hero text-foreground text-balance md:text-display">
          See what your AI agents actually do
        </h1>
        <p className="mt-[var(--space-2)] max-w-xl text-body text-foreground-muted">
          AgentScope normalizes traces from heterogeneous sources into one calm window — sessions,
          tokens, tools, and data quality.
        </p>
        <div className="mt-[var(--space-3)] flex flex-wrap items-center gap-[var(--space-2)]">
          {authenticated ? (
            <Button asChild size="lg">
              <Link to="/overview">Open app</Link>
            </Button>
          ) : (
            <>
              <Button asChild size="lg">
                <Link to="/register">Get started</Link>
              </Button>
              <Button asChild variant="text">
                <Link to="/login">Sign in</Link>
              </Button>
            </>
          )}
        </div>
      </div>

      <BentoGrid data-reveal="hero">
        <BentoModule
          cols={6}
          rows={2}
          interactive
          padding="none"
          className="min-h-80 overflow-hidden"
          data-preview
        >
          <DashboardPreview />
        </BentoModule>
      </BentoGrid>
    </section>
  )
}
