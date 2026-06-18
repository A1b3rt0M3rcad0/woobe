import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'
import { Topbar } from '@/components/layout/Topbar'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'

export function DashboardLayout() {
  const { pathname } = useLocation()
  const hideSidebar = pathname === '/organizations' || /^\/organizations\/[^/]+\/projects$/.test(pathname) || pathname.includes('/playground')
  const isProjectOverview = /^\/organizations\/[^/]+\/projects\/[^/]+\/?$/.test(pathname)
  const mainClassName = isProjectOverview
    ? 'project-overview-main min-w-0 flex-1 overflow-hidden p-3 sm:p-4 lg:p-5 2xl:p-6'
    : 'min-w-0 flex-1 overflow-hidden p-4 sm:p-6'

  return (
    <div className="flex h-screen min-w-0 bg-background">
      {!hideSidebar && (
        <div className="hidden shrink-0 lg:flex">
          <Sidebar />
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {!isProjectOverview && <Topbar />}
        <main className={mainClassName}>
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
