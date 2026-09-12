import { Outlet } from 'react-router-dom'
import { Card } from '@woobe/ui'

export function AuthLayout() {
  return (
    <main className="relative flex min-h-svh items-center justify-center overflow-hidden bg-background px-5 py-8 sm:px-8">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-100 [background-image:linear-gradient(rgba(148,163,184,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.025)_1px,transparent_1px)] [background-size:32px_32px]"
      />

      <Card className="relative w-full max-w-[392px] border-border bg-surface/[0.96] p-5 shadow-none">
        <Outlet />
      </Card>
    </main>
  )
}
