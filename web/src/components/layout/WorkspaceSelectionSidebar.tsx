import { useLocation, useNavigate } from 'react-router-dom'
import { Building2, FolderKanban, Play, type LucideIcon } from 'lucide-react'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { cn } from '@/lib/utils'
import { SidebarUserCard } from './SidebarUserCard'

function getRouteOrganizationId(pathname: string) {
  return pathname.match(/^\/organizations\/([^/]+)\/projects/)?.[1]
}

function getRouteProjectId(pathname: string) {
  return pathname.match(/^\/organizations\/[^/]+\/projects\/([^/]+)/)?.[1]
}

interface FlowItemProps {
  title: string
  description: string
  meta?: string
  icon: LucideIcon
  active?: boolean
  disabled?: boolean
  compact?: boolean
  onClick?: () => void
}

function FlowItem({ title, description, meta, icon: Icon, active, disabled, compact, onClick }: FlowItemProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'group w-full rounded-xl border bg-background/45 text-left transition-all',
        compact ? 'min-h-[112px] p-3' : 'p-4',
        active
          ? 'border-primary/60 bg-primary/10 shadow-[0_0_0_1px_rgba(59,130,246,0.18),0_18px_50px_rgba(37,99,235,0.08)]'
          : 'border-border/80 hover:border-primary/35 hover:bg-background/70',
        disabled && 'cursor-not-allowed opacity-45 hover:border-border/80 hover:bg-background/45',
      )}
    >
      <div className={cn('flex items-start gap-3', compact && 'flex-col')}>
        <span
          className={cn(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border transition-colors',
            active ? 'border-primary/40 bg-primary/15 text-primary-light' : 'border-border bg-surface text-muted group-hover:text-primary-light',
            disabled && 'group-hover:text-muted',
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-white">{title}</span>
          <span className="mt-1 block text-xs leading-5 text-muted">{description}</span>
          {meta && <span className="mt-3 block truncate font-mono text-xs text-primary-light">{meta}</span>}
        </span>
      </div>
    </button>
  )
}

export function WorkspaceSelectionSidebar({ compact = false }: { compact?: boolean }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { organizations, projects, currentOrganization, currentProject } = useWorkspace()

  const routeOrganizationId = getRouteOrganizationId(pathname)
  const routeProjectId = getRouteProjectId(pathname)
  const routeOrganization = routeOrganizationId ? organizations.find((organization) => organization.id === routeOrganizationId) : null
  const routeProject = routeProjectId ? projects.find((project) => project.id === routeProjectId) : null
  const selectedOrganization = routeOrganization ?? currentOrganization ?? null
  const selectedProject = routeProject ?? currentProject ?? null
  const hasOrganization = Boolean(selectedOrganization)
  const isOrganizationsView = pathname === '/organizations'
  const isProjectsView = Boolean(routeOrganizationId)

  const flowItems = (
    <>
      <FlowItem
        title="Organizations"
        description={selectedOrganization ? 'Current organization' : 'Select or create an organization'}
        meta={selectedOrganization?.name}
        icon={Building2}
        active={isOrganizationsView}
        compact={compact}
        onClick={() => navigate('/organizations')}
      />

      <FlowItem
        title="Projects"
        description={
          !hasOrganization
            ? 'Select an organization first'
            : selectedProject
              ? 'Current project'
              : 'Select or create a project'
        }
        meta={selectedProject?.name}
        icon={FolderKanban}
        active={isProjectsView}
        disabled={!selectedOrganization}
        compact={compact}
        onClick={() => selectedOrganization && navigate(`/organizations/${selectedOrganization.id}/projects`)}
      />
    </>
  )

  if (compact) {
    return (
      <div className="border-b border-border bg-surface lg:hidden">
        <div className="grid grid-cols-2 gap-2 p-3">{flowItems}</div>
      </div>
    )
  }

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-border bg-surface">
      <div className="border-b border-border p-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Play className="h-4 w-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">ProjectRAI</p>
            <p className="text-xs text-muted">Workspace selection</p>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-3 p-3">{flowItems}</div>
      </ScrollArea>

      <SidebarUserCard />
    </aside>
  )
}
