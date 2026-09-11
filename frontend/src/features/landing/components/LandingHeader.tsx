import { Link } from '@tanstack/react-router'

import { Button } from '@/components/ui/Button'
import { PublicHeader } from '@/components/ui/PublicHeader'

export interface LandingHeaderProps {
  authenticated: boolean
}

export function LandingHeader({ authenticated }: LandingHeaderProps) {
  return (
    <PublicHeader
      trailing={
        authenticated ? (
          <Button asChild variant="text">
            <Link to="/overview">Open app</Link>
          </Button>
        ) : (
          <Button asChild variant="text">
            <Link to="/login">Sign in</Link>
          </Button>
        )
      }
    />
  )
}
