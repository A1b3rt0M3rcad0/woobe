import { useEffect, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import { LoadingState } from '@/components/common/LoadingState'

interface RedirectLocation {
  pathname?: string
  search?: string
  hash?: string
}

export function resolvePublicRouteTarget(
  postAuthTarget: string | null,
  from?: RedirectLocation,
): string {
  if (postAuthTarget) return postAuthTarget
  if (from?.pathname) {
    return `${from.pathname}${from.search ?? ''}${from.hash ?? ''}`
  }
  return '/dashboard'
}

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const {
    isAuthenticated,
    isLoading,
    isInitializing,
    postAuthTarget,
    clearPostAuthTarget,
  } = useAuth()
  const location = useLocation()

  useEffect(() => {
    if (isAuthenticated && !isLoading && !isInitializing && postAuthTarget) {
      clearPostAuthTarget()
    }
  }, [clearPostAuthTarget, isAuthenticated, isInitializing, isLoading, postAuthTarget])

  if (isLoading || isInitializing) {
    return <LoadingState variant="fullscreen" layout="auth" message="Checking authentication..." />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}

export function PublicRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, postAuthTarget } = useAuth()
  const location = useLocation()
  const from = (location.state as { from?: RedirectLocation } | null)?.from

  if (isAuthenticated) {
    return <Navigate to={resolvePublicRouteTarget(postAuthTarget, from)} replace />
  }

  return <>{children}</>
}
