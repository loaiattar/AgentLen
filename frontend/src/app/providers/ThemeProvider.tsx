import { useEffect, useMemo, useState, type ReactNode } from 'react'

import { applyTheme, readTheme, THEME_STORAGE_KEY, type Theme } from '@/app/providers/theme'
import { ThemeContext, type ThemeContextValue } from '@/app/providers/useTheme'

function persistTheme(theme: Theme) {
  applyTheme(theme)
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    // Preference persistence is optional.
  }
}

function hasStoredTheme() {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
    return stored === 'dark' || stored === 'light'
  } catch {
    return false
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    const initial = readTheme()
    applyTheme(initial)
    return initial
  })

  useEffect(() => {
    if (hasStoredTheme() || typeof window.matchMedia !== 'function') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      const next = media.matches ? 'dark' : 'light'
      setThemeState(next)
      applyTheme(next)
    }
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      setTheme: (next) => {
        setThemeState(next)
        persistTheme(next)
      },
      toggleTheme: () => {
        setThemeState((current) => {
          const next = current === 'dark' ? 'light' : 'dark'
          persistTheme(next)
          return next
        })
      },
    }),
    [theme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
