import { useState, type FormEvent } from 'react'
import { Link, useRouter } from '@tanstack/react-router'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useLoginMutation, useRegisterMutation } from '@/features/auth/api/auth.mutations'
import { fieldForAuthError, messageForAuthError } from '@/features/auth/lib/errors'
import { resolvePostAuthPath } from '@/features/auth/lib/redirect'
import {
  validateEmail,
  validatePassword,
  validatePasswordConfirmation,
} from '@/features/auth/lib/validation'

export interface AuthCardProps {
  mode: 'signin' | 'signup'
  redirect?: string
}

interface FieldErrors {
  email?: string
  password?: string
  confirmation?: string
}

export function AuthCard({ mode, redirect }: AuthCardProps) {
  const router = useRouter()
  const login = useLoginMutation()
  const register = useRegisterMutation()
  const isSignup = mode === 'signup'
  const pending = login.isPending || register.isPending

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | undefined>()
  const [success, setSuccess] = useState(false)

  function validate(showAll = false): FieldErrors {
    const next: FieldErrors = {}
    const emailError = validateEmail(email)
    const passwordError = validatePassword(password)
    if (emailError) next.email = emailError
    if (passwordError) next.password = passwordError
    if (isSignup) {
      const confirmationError = validatePasswordConfirmation(password, confirmation)
      if (confirmationError) next.confirmation = confirmationError
    }
    if (showAll) setFieldErrors(next)
    return next
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(undefined)
    const errors = validate(true)
    if (Object.keys(errors).length > 0) return

    try {
      const credentials = { email: email.trim(), password }
      if (isSignup) {
        await register.mutateAsync(credentials)
      } else {
        await login.mutateAsync(credentials)
      }
      setSuccess(true)
      router.history.push(resolvePostAuthPath(redirect))
    } catch (error) {
      const message = messageForAuthError(
        error,
        isSignup ? 'Unable to create the account' : 'Unable to sign in',
      )
      const field = fieldForAuthError(error)
      if (field === 'form') {
        setFormError(message)
      } else {
        setFieldErrors((current) => ({ ...current, [field]: message }))
      }
    }
  }

  const hasFieldErrors = Boolean(fieldErrors.email || fieldErrors.password || fieldErrors.confirmation)
  const submitDisabled =
    pending || success || hasFieldErrors || !email || !password || (isSignup && !confirmation)

  return (
    <section className="glass-module w-full max-w-md p-[var(--space-4)]">
      <p className="text-meta font-medium tracking-[0.14em] text-foreground-subtle uppercase">
        {isSignup ? 'Create account' : 'Welcome back'}
      </p>
      <h1 className="mt-[var(--space-1)] font-display text-page text-foreground">
        {isSignup ? 'Sign up' : 'Sign in'}
      </h1>
      <p className="mt-[var(--space-1)] text-body text-foreground-muted">
        {isSignup
          ? 'One email, one password. Then the dashboard.'
          : 'Continue to AgentScope.'}
      </p>

      <form className="mt-[var(--space-4)] grid gap-[var(--space-3)]" onSubmit={onSubmit} noValidate>
        <Field label="Email" htmlFor="auth-email" error={fieldErrors.email}>
          <Input
            id="auth-email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            error={Boolean(fieldErrors.email)}
            disabled={pending || success}
            onChange={(event) => {
              setEmail(event.target.value)
              if (fieldErrors.email) setFieldErrors((current) => ({ ...current, email: undefined }))
            }}
            onBlur={() => {
              const emailError = validateEmail(email)
              setFieldErrors((current) => ({ ...current, email: emailError }))
            }}
          />
        </Field>

        <Field label="Password" htmlFor="auth-password" error={fieldErrors.password}>
          <Input
            id="auth-password"
            name="password"
            type="password"
            autoComplete={isSignup ? 'new-password' : 'current-password'}
            value={password}
            error={Boolean(fieldErrors.password)}
            disabled={pending || success}
            onChange={(event) => {
              setPassword(event.target.value)
              if (fieldErrors.password) setFieldErrors((current) => ({ ...current, password: undefined }))
            }}
            onBlur={() => {
              const passwordError = validatePassword(password)
              setFieldErrors((current) => ({ ...current, password: passwordError }))
            }}
          />
        </Field>

        {isSignup ? (
          <Field label="Confirm password" htmlFor="auth-confirmation" error={fieldErrors.confirmation}>
            <Input
              id="auth-confirmation"
              name="confirmation"
              type="password"
              autoComplete="new-password"
              value={confirmation}
              error={Boolean(fieldErrors.confirmation)}
              disabled={pending || success}
              onChange={(event) => {
                setConfirmation(event.target.value)
                if (fieldErrors.confirmation) {
                  setFieldErrors((current) => ({ ...current, confirmation: undefined }))
                }
              }}
              onBlur={() => {
                const confirmationError = validatePasswordConfirmation(password, confirmation)
                setFieldErrors((current) => ({ ...current, confirmation: confirmationError }))
              }}
            />
          </Field>
        ) : null}

        {formError ? (
          <p role="alert" className="text-secondary text-error">
            {formError}
          </p>
        ) : null}

        {success ? (
          <p role="status" className="text-secondary text-primary">
            {isSignup ? 'Account created. Opening AgentScope…' : 'Signed in. Opening AgentScope…'}
          </p>
        ) : null}

        <Button type="submit" variant="primary" loading={pending} disabled={submitDisabled}>
          {isSignup ? 'Create account' : 'Sign in'}
        </Button>
      </form>

      <p className="mt-[var(--space-3)] text-secondary text-foreground-muted">
        {isSignup ? 'Already have an account? ' : 'Need an account? '}
        <Button asChild variant="text" size="sm" className="inline h-auto">
          {isSignup ? (
            <Link to="/login" search={redirect ? { redirect } : {}}>
              Sign in
            </Link>
          ) : (
            <Link to="/register" search={redirect ? { redirect } : {}}>
              Sign up
            </Link>
          )}
        </Button>
      </p>
    </section>
  )
}
