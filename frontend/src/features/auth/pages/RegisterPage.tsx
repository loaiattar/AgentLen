import { useSearch } from '@tanstack/react-router'

import { PublicHeader } from '@/components/ui/PublicHeader'
import { AuthCard } from '@/features/auth/components/AuthCard'

export function RegisterPage() {
  const { redirect } = useSearch({ from: '/_public/register' })

  return (
    <div className="flex min-h-dvh flex-col">
      <PublicHeader />
      <main className="flex flex-1 items-center justify-center px-[var(--space-2)] py-[var(--space-4)]">
        <AuthCard mode="signup" redirect={redirect} />
      </main>
    </div>
  )
}
