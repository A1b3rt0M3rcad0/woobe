import { useCallback, useEffect, useState } from 'react'
import { Drawer } from '@woobe/ui'
import { Topbar } from '@/components/layout/Topbar'
import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'
import { WorkspaceSelectionSidebar } from '@/components/layout/WorkspaceSelectionSidebar'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'

export function DashboardLayout() {
  const { pathname } = useLocation()
  const [navigationOpen, setNavigationOpen] = useState(false)
  const closeNavigation = useCallback(() => setNavigationOpen(false), [])
  useEffect(closeNavigation, [pathname, closeNavigation])
  const isWorkspaceSelection = pathname === '/workspaces' || /^\/workspaces\/[^/]+\/projects$/.test(pathname)
  const isSetupFlow = /\/setup\/?$/.test(pathname)
  const isNetworkWorkspace = /\/projects\/[^/]+\/networks\/[^/]+\/?$/.test(pathname)
  const isPlayground = pathname.includes('/playground')
  const hideSidebar = isPlayground || isSetupFlow || isNetworkWorkspace || isPlayground
  const isProjectOverview = /^\/workspaces\/[^/]+\/projects\/[^/]+\/?$/.test(pathname)
  const isProjectResource = /^\/workspaces\/[^/]+\/projects\/[^/]+\/(?:network|networks|agents|knowledge|tools|skills|models|credentials|api-keys|chat-surfaces|usage|traces)\/?$/.test(pathname)
  const mainClassName = isSetupFlow || isNetworkWorkspace || isPlayground
    ? 'min-h-0 min-w-0 flex-1 overflow-hidden'
    : isProjectOverview
      ? 'project-overview-main min-h-0 min-w-0 flex-1 overflow-y-auto p-ui-lg sm:p-ui-xxl'
      : isProjectResource
        ? 'scrollbar-thin min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden bg-background bg-technical-grid'
        : isWorkspaceSelection
          ? 'scrollbar-thin min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden p-4 sm:p-5 lg:p-5 2xl:p-6 bg-technical-grid'
          : 'scrollbar-thin min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden p-4 sm:p-6'

  return (
    <div className="flex h-svh min-w-0 overflow-hidden bg-background">
      <a href="#main-content" className="sr-only z-focus rounded-control bg-primary px-ui-lg py-ui-sm text-primary-foreground focus:not-sr-only focus:absolute focus:left-4 focus:top-4">Skip to content</a>
      {!hideSidebar && (
        <div className="hidden min-h-0 shrink-0 lg:flex">
          {isWorkspaceSelection ? <WorkspaceSelectionSidebar /> : <Sidebar />}
        </div>
      )}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {!hideSidebar && <Topbar onOpenNavigation={() => setNavigationOpen(true)} />}
        {isWorkspaceSelection && <WorkspaceSelectionSidebar compact />}
        <main id="main-content" tabIndex={-1} className={mainClassName}>
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
      {!hideSidebar && <Drawer open={navigationOpen} onClose={closeNavigation} title="Navigation" className="max-w-xs [&>div:last-child]:p-0">
        {isWorkspaceSelection ? <WorkspaceSelectionSidebar /> : <Sidebar />}
      </Drawer>}
    </div>
  )
}
