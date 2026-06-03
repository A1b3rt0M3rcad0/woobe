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
  token: string
  user: User
}

export interface RegisterRequest {
  email: string
  password: string
  organization_name: string
}

export interface Organization {
  id: string
  name: string
  slug: string
  status?: string
  created_at?: string
}
