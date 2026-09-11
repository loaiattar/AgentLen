import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'

import { loginRequest, logoutRequest, registerRequest } from '@/features/auth/api/auth.api'
import { authKeys } from '@/features/auth/api/auth.keys'
import type { AuthCredentials } from '@/features/auth/types'
import { clearSessionToken, setSessionToken } from '@/lib/auth/session'

export function useLoginMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: loginRequest,
    onSuccess: (data) => {
      setSessionToken(data.token)
      queryClient.setQueryData(authKeys.me(), data.user)
    },
  })
}

export function useRegisterMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (body: AuthCredentials) => {
      await registerRequest(body)
      return loginRequest(body)
    },
    onSuccess: (data) => {
      setSessionToken(data.token)
      queryClient.setQueryData(authKeys.me(), data.user)
    },
  })
}

export function useLogoutMutation() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  return useMutation({
    mutationFn: logoutRequest,
    onSettled: async () => {
      clearSessionToken()
      queryClient.removeQueries({ queryKey: authKeys.all })
      await navigate({ to: '/' })
    },
  })
}
