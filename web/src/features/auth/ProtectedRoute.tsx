import { type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import { LoadingState } from '@/components/common/LoadingState'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, isInitializing } = useAuth()
  const location = useLocation()

  if (isLoading || isInitializing) {
    return <LoadingState message="Checking authentication..." />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}

export function PublicRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const location = useLocation()
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/organizations'

  if (isAuthenticated) {
    return <Navigate to={from} replace />
  }

  return <>{children}</>
}
