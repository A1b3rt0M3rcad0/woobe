import { post, get } from '@/lib/api/client'
import type { LoginRequest, LoginResponse, RegisterRequest, User, Organization } from './types'

export async function login(data: LoginRequest): Promise<LoginResponse> {
  return post<LoginResponse>('/identity/auth/login', data)
}

export async function register(data: RegisterRequest): Promise<LoginResponse> {
  return post<LoginResponse>('/identity/auth/register', data)
}

export async function refreshSession(): Promise<LoginResponse> {
  return post<LoginResponse>('/identity/auth/refresh')
}

export async function endSession(): Promise<void> {
  await post<void>('/identity/auth/logout')
}

export async function getCurrentUser(): Promise<User> {
  return get<User>('/identity/users/me')
}

export async function getOrganizations(): Promise<Organization[]> {
  return get<Organization[]>('/identity/organizations')
}
