import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'
import { WorkspaceSelectionSidebar } from '@/components/layout/WorkspaceSelectionSidebar'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'

export function DashboardLayout() {
  const { pathname } = useLocation()
  const isWorkspaceSelection = pathname === '/workspaces' || /^\/workspaces\/[^/]+\/projects$/.test(pathname)
  const isSetupFlow = /\/setup\/?$/.test(pathname)
  const isNetworkWorkspace = /\/projects\/[^/]+\/networks\/[^/]+\/?$/.test(pathname)
  const hideSidebar = pathname.includes('/playground') || isSetupFlow || isNetworkWorkspace
  const isProjectOverview = /^\/workspaces\/[^/]+\/projects\/[^/]+\/?$/.test(pathname)
  const mainClassName = isSetupFlow || isNetworkWorkspace
    ? 'min-h-0 min-w-0 flex-1 overflow-hidden'
    : isProjectOverview
      ? 'project-overview-main scrollbar-thin min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden p-3 sm:p-4 lg:p-5 2xl:p-6'
      : isWorkspaceSelection
        ? 'scrollbar-thin min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden p-4 sm:p-5 lg:p-5 2xl:p-6 [background-image:linear-gradient(rgba(148,163,184,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.025)_1px,transparent_1px)] [background-size:32px_32px]'
        : 'scrollbar-thin min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden p-4 sm:p-6'

  return (
    <div className="flex h-screen min-w-0 overflow-hidden bg-background">
      {!hideSidebar && (
        <div className="hidden min-h-0 shrink-0 lg:flex">
          {isWorkspaceSelection ? <WorkspaceSelectionSidebar /> : <Sidebar />}
        </div>
      )}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {isWorkspaceSelection && <WorkspaceSelectionSidebar compact />}
        <main className={mainClassName}>
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
