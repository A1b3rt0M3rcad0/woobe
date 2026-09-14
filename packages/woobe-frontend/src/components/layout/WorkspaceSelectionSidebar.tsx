import { useLocation, useNavigate } from 'react-router-dom'
import { Building2, FolderKanban, Orbit, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { SidebarUserCard } from './SidebarUserCard'

function getRouteWorkspaceId(pathname: string) {
  return pathname.match(/^\/workspaces\/([^/]+)\/projects/)?.[1]
}

interface FlowItemProps {
  title: string
  description: string
  icon: LucideIcon
  active?: boolean
  disabled?: boolean
  compact?: boolean
  onClick?: () => void
}

function FlowItem({ title, description, icon: Icon, active, disabled, compact, onClick }: FlowItemProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      title={description}
      className={cn(
        'group flex h-control-nav w-full items-center gap-ui-sm rounded-technical border px-ui-sm text-left font-mono text-product-small transition-colors',
        active
          ? 'border-primary/40 bg-primary/[0.12] text-slate-50'
          : 'border-transparent text-slate-300 hover:border-border hover:bg-accent/40 hover:text-slate-50',
        disabled && 'cursor-not-allowed opacity-40 hover:border-transparent hover:bg-transparent hover:text-slate-300',
        compact && 'justify-center px-ui-md sm:justify-start',
      )}
    >
      <Icon
        className={cn(
          'h-icon w-icon shrink-0',
          active ? 'text-primary-light' : 'text-muted-foreground group-hover:text-slate-200',
          disabled && 'group-hover:text-muted-foreground',
        )}
      />
      <span className={cn('truncate', compact && 'hidden sm:inline')}>{title}</span>
      {!compact && disabled && <span className="ml-auto text-system-meta uppercase tracking-[0.08em] text-muted-foreground">locked</span>}
    </button>
  )
}

export function WorkspaceSelectionSidebar({ compact = false }: { compact?: boolean }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()

  const routeWorkspaceId = getRouteWorkspaceId(pathname)
  const hasRouteWorkspace = Boolean(routeWorkspaceId)
  const isWorkspacesView = pathname === '/workspaces'
  const isProjectsView = hasRouteWorkspace

  const flowItems = (
    <>
      <FlowItem
        title="Workspaces"
        description="Select or create a workspace"
        icon={Building2}
        active={isWorkspacesView}
        compact={compact}
        onClick={() => navigate('/workspaces')}
      />
      <FlowItem
        title="Projects"
        description={hasRouteWorkspace ? 'Select or create a project' : 'Select a workspace first'}
        icon={FolderKanban}
        active={isProjectsView}
        disabled={!hasRouteWorkspace}
        compact={compact}
        onClick={() => routeWorkspaceId && navigate(`/workspaces/${routeWorkspaceId}/projects`)}
      />
    </>
  )

  if (compact) {
    return (
      <div className="border-b border-border bg-surface lg:hidden">
        <div className="grid grid-cols-2 gap-ui-xs p-ui-sm">{flowItems}</div>
      </div>
    )
  }

  return (
    <aside className="flex w-project-sidebar shrink-0 flex-col border-r border-border bg-surface">
      <header className="flex h-project-sidebar-header shrink-0 items-center gap-ui-sm border-b border-border px-ui-xl">
        <div className="flex h-control-sm w-control-sm items-center justify-center text-slate-50" aria-hidden="true">
          <Orbit className="h-icon-brand w-icon-brand" strokeWidth={1.7} />
        </div>
        <div className="min-w-0">
          <p className="font-mono text-heading-sm font-bold tracking-[0.02em] text-slate-50">WOOBE</p>
          <p className="mt-ui-hairline font-mono text-system-label uppercase tracking-[0.12em] text-muted-foreground">control plane</p>
        </div>
      </header>

      <nav className="flex-1 overflow-y-auto px-ui-md py-ui-lg" aria-label="Workspace navigation">
        <p className="mb-ui-sm px-ui-sm font-mono text-system-label font-bold uppercase tracking-[0.15em] text-muted-foreground">
          Workspace
        </p>
        <div className="grid gap-ui-hairline">{flowItems}</div>
      </nav>

      <SidebarUserCard variant="technical" />
    </aside>
  )
}
