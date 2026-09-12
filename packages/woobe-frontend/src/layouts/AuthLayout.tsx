import { Outlet } from 'react-router-dom'
import { Card } from '@woobe/ui'

export function AuthLayout() {
  return (
    <main className="flex min-h-svh items-center justify-center bg-background px-5 py-8 sm:px-8">
      <Card className="w-full max-w-[408px] border-border bg-surface p-5 shadow-none sm:p-6">
        <Outlet />
      </Card>
    </main>
  )
}
