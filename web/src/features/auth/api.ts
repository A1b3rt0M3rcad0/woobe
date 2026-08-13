import { get, post } from '@/lib/api/client'
import type {
  InstanceStatus,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  User,
} from './types'

export async function login(data: LoginRequest): Promise<LoginResponse> {
  return post<LoginResponse>('/identity/auth/login', data)
}

export async function getInstanceStatus(): Promise<InstanceStatus> {
  return get<InstanceStatus>('/identity/instance/status')
}

export async function register(data: RegisterRequest): Promise<RegisterResponse> {
  const instance = await getInstanceStatus()
  if (!instance.initialized) {
    return post<RegisterResponse>('/identity/instance/bootstrap', data)
  }
  return post<RegisterResponse>('/identity/auth/register', data)
}

export async function logout(): Promise<void> {
  await post('/identity/auth/logout', {})
}

export async function getCurrentUser(): Promise<User> {
  return get<User>('/identity/users/me')
}
