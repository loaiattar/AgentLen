import { useSyncExternalStore } from 'react'

const TOKEN_KEY = 'agentscope.session-token'
const listeners = new Set<() => void>()

function notify() {
  listeners.forEach((listener) => {
    listener()
  })
}

function readToken(): string | null {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function getSessionToken(): string | null {
  return readToken()
}

export function setSessionToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token)
  notify()
}

export function clearSessionToken() {
  window.localStorage.removeItem(TOKEN_KEY)
  notify()
}

export function subscribeSession(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function useSessionToken() {
  return useSyncExternalStore(subscribeSession, getSessionToken, () => null)
}
