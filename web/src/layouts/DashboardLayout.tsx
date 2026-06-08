import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'
import { Topbar } from '@/components/layout/Topbar'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'

export function DashboardLayout() {
  const { pathname } = useLocation()
  const hideSidebar = pathname === '/organizations' || /^\/organizations\/[^/]+\/projects$/.test(pathname) || pathname.includes('/playground')

  return (
    <div className="flex h-screen bg-background">
      {!hideSidebar && <Sidebar />}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-hidden p-6">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
