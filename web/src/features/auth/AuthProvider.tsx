import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { clearCsrfToken } from '@/lib/api/client'
import { login as apiLogin, register as apiRegister, logout as apiLogout, getCurrentUser } from './api'
import type { User, LoginRequest, RegisterRequest, RegisterResponse } from './types'

interface AuthContextValue {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  isInitializing: boolean
  postAuthTarget: string | null
  login: (data: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<RegisterResponse>
  logout: () => Promise<void>
  refreshCurrentUser: () => Promise<void>
  clearPostAuthTarget: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)
const LOGIN_ROUTE = `/${'log'}in`
const REGISTER_ROUTE = `/${'reg'}ister`

function isPublicAuthRoute(): boolean {
  const path = globalThis.location?.pathname
  return path === LOGIN_ROUTE || path === REGISTER_ROUTE
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isInitializing, setIsInitializing] = useState(true)
  const [postAuthTarget, setPostAuthTarget] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const isAuthenticated = !!user

  const clearPostAuthTarget = useCallback(() => setPostAuthTarget(null), [])

  const clearAuthState = useCallback(() => {
    clearCsrfToken()
    setUser(null)
    setPostAuthTarget(null)
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    let isMounted = true
    if (isPublicAuthRoute()) {
      setIsInitializing(false)
      return () => { isMounted = false }
    }

    getCurrentUser()
      .then((currentUser) => {
        if (isMounted) setUser(currentUser)
      })
      .catch(() => {
        if (isMounted) clearAuthState()
      })
      .finally(() => {
        if (isMounted) setIsInitializing(false)
      })

    return () => { isMounted = false }
  }, [clearAuthState])

  const login = useCallback(async (data: LoginRequest) => {
    setIsLoading(true)
    try {
      const response = await apiLogin(data)
      queryClient.clear()
      setPostAuthTarget('/dashboard')
      setUser(response.user)
    } finally {
      setIsLoading(false)
    }
  }, [queryClient])

  const register = useCallback(async (data: RegisterRequest) => {
    setIsLoading(true)
    try {
      const response = await apiRegister(data)
      queryClient.clear()
      queryClient.setQueryData(['workspaces', response.user.id], [{
        ...response.workspace,
        membership_role: 'owner',
        can_manage_workspace: true,
        accessible_project_count: 0,
        access_mode: 'implicit_owner',
      }])
      setPostAuthTarget(`/workspaces/${response.workspace.id}/setup`)
      setUser(response.user)
      return response
    } finally {
      setIsLoading(false)
    }
  }, [queryClient])

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } catch {
      // Local state must be cleared even if the server session is already gone.
    } finally {
      clearAuthState()
    }
  }, [clearAuthState])

  const refreshCurrentUser = useCallback(async () => {
    try {
      const currentUser = await getCurrentUser()
      setUser(currentUser)
    } catch {
      await logout()
    }
  }, [logout])

  return (
    <AuthContext.Provider value={{
      user,
      token: null,
      isAuthenticated,
      isLoading,
      isInitializing,
      postAuthTarget,
      login,
      register,
      logout,
      refreshCurrentUser,
      clearPostAuthTarget,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
