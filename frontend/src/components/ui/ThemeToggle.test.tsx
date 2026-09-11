import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { act } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'

import { ThemeProvider } from '@/app/providers/ThemeProvider'
import { THEME_STORAGE_KEY } from '@/app/providers/theme'
import { ThemeToggle } from '@/components/ui/ThemeToggle'

const osListeners = new Set<() => void>()
let osPrefersDark = false

beforeEach(() => {
  window.localStorage.removeItem(THEME_STORAGE_KEY)
  document.documentElement.classList.remove('dark')
  document.documentElement.style.colorScheme = ''
  osListeners.clear()
  osPrefersDark = false
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      get matches() {
        return osPrefersDark
      },
      media: query,
      addEventListener: (_: string, listener: () => void) => osListeners.add(listener),
      removeEventListener: (_: string, listener: () => void) => osListeners.delete(listener),
    }),
  })
})

/** Flip the OS preference and notify whoever subscribed, like the real media query. */
function setOsPreference(prefersDark: boolean) {
  osPrefersDark = prefersDark
  for (const listener of osListeners) listener()
}

describe('ThemeToggle', () => {
  it('switches the document between light and dark', async () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }))
    expect(document.documentElement).toHaveClass('dark')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')

    await userEvent.click(screen.getByRole('button', { name: 'Switch to light theme' }))
    expect(document.documentElement).not.toHaveClass('dark')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })

  it('follows the OS while no theme was picked', async () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    )

    await act(async () => setOsPreference(true))

    expect(document.documentElement).toHaveClass('dark')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBeNull()
  })

  it('stops following the OS once the user picks a theme', async () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }))
    await userEvent.click(screen.getByRole('button', { name: 'Switch to light theme' }))
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')

    // Scheduled night mode, macOS auto-appearance: the OS flips under the user.
    await act(async () => setOsPreference(true))

    expect(document.documentElement).not.toHaveClass('dark')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })
})
