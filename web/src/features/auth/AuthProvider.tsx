import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { login as apiLogin, register as apiRegister, getCurrentUser } from './api'
import { getToken, setToken, clearToken } from '@/lib/auth/token'
import type { User, LoginRequest, RegisterRequest, Organization } from './types'

interface AuthContextValue {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  isInitializing: boolean
  login: (data: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => void
  refreshCurrentUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setTokenState] = useState<string | null>(getToken())
  const [isLoading, setIsLoading] = useState(false)
  const [isInitializing, setIsInitializing] = useState(true)
  const queryClient = useQueryClient()

  const isAuthenticated = !!token

  useEffect(() => {
    if (token && !user) {
      getCurrentUser()
        .then((u) => setUser(u))
        .catch(() => {
          clearToken()
          setTokenState(null)
        })
        .finally(() => setIsInitializing(false))
    } else {
      setIsInitializing(false)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(async (data: LoginRequest) => {
    setIsLoading(true)
    try {
      const res = await apiLogin(data)
      setToken(res.token)
      setTokenState(res.token)
      setUser(res.user)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const register = useCallback(async (data: RegisterRequest) => {
    setIsLoading(true)
    try {
      const res = await apiRegister(data)
      setToken(res.token)
      setTokenState(res.token)
      setUser(res.user)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setTokenState(null)
    setUser(null)
    queryClient.clear()
  }, [queryClient])

  const refreshCurrentUser = useCallback(async () => {
    try {
      const u = await getCurrentUser()
      setUser(u)
    } catch {
      logout()
    }
  }, [logout])

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
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
