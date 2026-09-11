import { ApiError } from '@/lib/api/client'

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

export function messageForAuthError(error: unknown, fallback: string): string {
  if (!isApiError(error)) return fallback

  switch (error.code) {
    case 'INVALID_CREDENTIALS':
      return 'Email or password is incorrect'
    case 'CONFLICT':
      return 'An account already exists for this email'
    case 'INVALID_EMAIL':
      return 'Enter a valid email'
    case 'WEAK_PASSWORD':
      return 'Password must be at least 8 characters'
    default:
      return error.message || fallback
  }
}

export function fieldForAuthError(error: unknown): 'email' | 'password' | 'form' {
  if (!isApiError(error)) return 'form'
  if (error.code === 'CONFLICT' || error.code === 'INVALID_EMAIL') return 'email'
  if (error.code === 'WEAK_PASSWORD') return 'password'
  return 'form'
}
