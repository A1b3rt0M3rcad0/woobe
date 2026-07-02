import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { clearCsrfToken } from '@/lib/api/client'
import { login as apiLogin, register as apiRegister, logout as apiLogout, getCurrentUser } from './api'
import type { User, LoginRequest, RegisterRequest, Organization } from './types'

interface AuthContextValue {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  isInitializing: boolean
  login: (data: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => Promise<void>
  refreshCurrentUser: () => Promise<void>
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
  const queryClient = useQueryClient()

  const isAuthenticated = !!user

  const clearAuthState = useCallback(() => {
    clearCsrfToken()
    setUser(null)
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    let isMounted = true

    if (isPublicAuthRoute()) {
      setIsInitializing(false)
      return () => {
        isMounted = false
      }
    }

    getCurrentUser()
      .then((u) => {
        if (isMounted) setUser(u)
      })
      .catch(() => {
        if (isMounted) clearAuthState()
      })
      .finally(() => {
        if (isMounted) setIsInitializing(false)
      })

    return () => {
      isMounted = false
    }
  }, [clearAuthState])

  const login = useCallback(async (data: LoginRequest) => {
    setIsLoading(true)
    try {
      const res = await apiLogin(data)
      setUser(res.user)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const register = useCallback(async (data: RegisterRequest) => {
    setIsLoading(true)
    try {
      const res = await apiRegister(data)
      setUser(res.user)
    } finally {
      setIsLoading(false)
    }
  }, [])

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
      const u = await getCurrentUser()
      setUser(u)
    } catch {
      await logout()
    }
  }, [logout])

  return (
    <AuthContext.Provider
      value={{
        user,
        token: null,
        isAuthenticated,
        isLoading,
        isInitializing,
        login,
        register,
        logout,
        refreshCurrentUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
