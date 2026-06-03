import { Outlet } from 'react-router-dom'

export function AuthLayout() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-white">ProjectRAI</h1>
          <p className="text-sm text-muted mt-1">Production runtime for AI agents</p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
