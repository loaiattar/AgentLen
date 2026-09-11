const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const MIN_PASSWORD_LENGTH = 8
const MAX_PASSWORD_BYTES = 72

export function validateEmail(email: string): string | undefined {
  const normalized = email.trim()
  if (!normalized) return 'Email is required'
  if (!EMAIL_PATTERN.test(normalized.toLowerCase())) return 'Enter a valid email'
  return undefined
}

export function validatePassword(password: string): string | undefined {
  if (!password) return 'Password is required'
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters`
  }
  if (new TextEncoder().encode(password).length > MAX_PASSWORD_BYTES) {
    return `Password must be at most ${MAX_PASSWORD_BYTES} bytes`
  }
  return undefined
}

export function validatePasswordConfirmation(password: string, confirmation: string): string | undefined {
  if (!confirmation) return 'Confirm your password'
  if (confirmation !== password) return 'Passwords do not match'
  return undefined
}
