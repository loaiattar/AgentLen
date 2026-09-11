import { useRef } from 'react'

import { LandingFooter } from '@/features/landing/components/LandingFooter'
import { LandingHeader } from '@/features/landing/components/LandingHeader'
import { LandingHero } from '@/features/landing/components/LandingHero'
import { HowItWorks } from '@/features/landing/components/HowItWorks'
import { AssistantSpotlight } from '@/features/landing/components/AssistantSpotlight'
import { useLandingMotion } from '@/features/landing/hooks/useLandingMotion'
import { useSessionToken } from '@/lib/auth/session'

export function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null)
  const token = useSessionToken()
  const authenticated = Boolean(token)

  useLandingMotion(containerRef)

  return (
    <div ref={containerRef} className="relative min-h-dvh">
      <LandingHeader authenticated={authenticated} />
      <main className="mx-auto flex max-w-7xl flex-col gap-[var(--space-6)] px-[var(--space-2)] pb-[var(--space-6)] md:px-[var(--space-4)]">
        <LandingHero authenticated={authenticated} />
        <HowItWorks />
        <AssistantSpotlight />
      </main>
      <LandingFooter />
    </div>
  )
}
