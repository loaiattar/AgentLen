export interface AuthUser {
  id: number
  email: string
  created_at: string
}

export interface LoginResponse {
  token: string
  user: AuthUser
}

export interface AuthCredentials {
  email: string
  password: string
}

