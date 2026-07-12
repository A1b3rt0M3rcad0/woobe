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

export interface Organization {
  id: string
  name: string
  slug: string
  status?: string
  created_at?: string
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

export interface RegisterResponse extends LoginResponse {
  organization: Organization
}
