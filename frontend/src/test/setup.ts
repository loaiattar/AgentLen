import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Testing Library does not unmount between tests on its own outside of its own
// globals setup, and a hook left mounted keeps its query subscriptions alive —
// which is exactly what the polling tests below are measuring.
afterEach(() => {
  cleanup()
})
