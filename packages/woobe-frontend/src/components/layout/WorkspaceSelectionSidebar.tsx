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
        'group flex h-9 w-full items-center gap-2.5 rounded-technical border px-2.5 text-left font-mono text-[11px] transition-colors',
        active
          ? 'border-primary/45 bg-primary/[0.12] text-slate-50'
          : 'border-transparent text-slate-300 hover:border-border hover:bg-accent/45 hover:text-slate-50',
        disabled && 'cursor-not-allowed opacity-40 hover:border-transparent hover:bg-transparent hover:text-slate-300',
        compact && 'justify-center px-3 sm:justify-start',
      )}
    >
      <Icon
        className={cn(
          'h-[15px] w-[15px] shrink-0',
          active ? 'text-primary-light' : 'text-muted-foreground group-hover:text-slate-200',
          disabled && 'group-hover:text-muted-foreground',
        )}
      />
      <span className={cn('truncate', compact && 'hidden sm:inline')}>{title}</span>
      {!compact && disabled && <span className="ml-auto text-[8px] uppercase tracking-[0.08em] text-muted">locked</span>}
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
        <div className="grid grid-cols-2 gap-1 p-2">{flowItems}</div>
      </div>
    )
  }

  return (
    <aside className="flex w-[258px] shrink-0 flex-col border-r border-border bg-surface">
      <header className="flex h-[72px] shrink-0 items-center gap-2.5 border-b border-border px-[18px]">
        <div className="flex h-[29px] w-[29px] items-center justify-center text-slate-50" aria-hidden="true">
          <Orbit className="h-[21px] w-[21px]" strokeWidth={1.7} />
        </div>
        <div className="min-w-0">
          <p className="font-mono text-sm font-bold tracking-[0.02em] text-slate-50">WOOBE</p>
          <p className="mt-px font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">control plane</p>
        </div>
      </header>

      <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Workspace navigation">
        <p className="mb-2 px-2 font-mono text-[9px] font-bold uppercase tracking-[0.15em] text-muted">
          Workspace
        </p>
        <div className="grid gap-[3px]">{flowItems}</div>
      </nav>

      <SidebarUserCard variant="technical" />
    </aside>
  )
}
