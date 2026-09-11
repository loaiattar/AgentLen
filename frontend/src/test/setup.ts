import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

import { THEME_STORAGE_KEY } from '@/app/providers/theme'

// Testing Library does not unmount between tests on its own outside of its own
// globals setup, and a hook left mounted keeps its query subscriptions alive —
// which is exactly what the polling tests below are measuring.
afterEach(() => {
  cleanup()
  window.localStorage.removeItem(THEME_STORAGE_KEY)
  document.documentElement.classList.remove('dark')
  document.documentElement.style.colorScheme = ''
})
