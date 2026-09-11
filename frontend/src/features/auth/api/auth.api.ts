import { apiClient } from '@/lib/api/client'
import type { AuthCredentials, AuthUser, LoginResponse } from '@/features/auth/types'

export function loginRequest(body: AuthCredentials) {
  return apiClient.post<LoginResponse>('/auth/login', body)
}

export function registerRequest(body: AuthCredentials) {
  return apiClient.post<AuthUser>('/auth/register', body)
}

export function logoutRequest() {
  return apiClient.post<void>('/auth/logout')
}

export function meRequest() {
  return apiClient.get<AuthUser>('/auth/me')
}
