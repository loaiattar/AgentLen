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
    if (typeof window.matchMedia !== 'function') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      // Re-checked on every change, not only at mount: the user may have picked
      // a theme since. Following the OS here would discard that choice and, as
      // this path does not persist, leave localStorage disagreeing with the UI
      // until the next reload flipped it back.
      if (hasStoredTheme()) return
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
        // `theme` from the closure, not a setState updater: an updater must be
        // pure. StrictMode runs it twice, and a concurrent render that is later
        // discarded would still have written the class and localStorage for a
        // transition that never commits. `setTheme` above already does this.
        const next = theme === 'dark' ? 'light' : 'dark'
        setThemeState(next)
        persistTheme(next)
      },
    }),
    [theme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
