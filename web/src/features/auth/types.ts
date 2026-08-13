export interface User {
  id: string
  email: string
  status?: string
  created_at?: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  token_type?: string
  expires_in?: number
  csrf?: string
  user: User
}

export interface RegisterRequest {
  email: string
  password: string
}

export type RegisterResponse = LoginResponse

export interface InstanceStatus {
  initialized: boolean
  instance_id: string | null
  signup_mode: 'bootstrap' | 'open' | 'invite_only' | 'disabled'
  telemetry_enabled: boolean
}
