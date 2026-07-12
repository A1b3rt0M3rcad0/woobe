import { post, get } from '@/lib/api/client'
import type { LoginRequest, LoginResponse, RegisterRequest, RegisterResponse, User, Organization } from './types'

export async function login(data: LoginRequest): Promise<LoginResponse> {
  return post<LoginResponse>('/identity/auth/login', data)
}

export async function register(data: RegisterRequest): Promise<RegisterResponse> {
  return post<RegisterResponse>('/identity/auth/register', data)
}

export async function logout(): Promise<void> {
  await post('/identity/auth/logout', {})
}

export async function getCurrentUser(): Promise<User> {
  return get<User>('/identity/users/me')
}

export async function getOrganizations(): Promise<Organization[]> {
  return get<Organization[]>('/identity/organizations')
}
