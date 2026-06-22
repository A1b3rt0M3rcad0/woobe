import { useLocation, useNavigate } from 'react-router-dom'
import { Building2, CheckCircle2, FolderKanban, LayoutDashboard, Lock, Plus, Play, Settings } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { cn } from '@/lib/utils'

function getRouteOrganizationId(pathname: string) {
  return pathname.match(/^\/organizations\/([^/]+)\/projects/)?.[1]
}

function StepBadge({ done, active, blocked }: { done?: boolean; active?: boolean; blocked?: boolean }) {
  if (done) return <CheckCircle2 className="h-4 w-4 text-primary-light" />
  if (blocked) return <Lock className="h-4 w-4 text-muted" />
  return <span className={cn('h-2.5 w-2.5 rounded-full', active ? 'bg-primary' : 'bg-border')} />
}

export function WorkspaceSelectionSidebar({ compact = false }: { compact?: boolean }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { organizations, projects, currentOrganization, currentProject, selectOrganization, selectProject } = useWorkspace()
  const routeOrganizationId = getRouteOrganizationId(pathname)
  const routeOrganization = routeOrganizationId ? organizations.find((organization) => organization.id === routeOrganizationId) : null
  const selectedOrganization = currentOrganization ?? routeOrganization ?? null
  const hasOrganization = Boolean(selectedOrganization)
  const hasProject = Boolean(currentProject)
  const isOrganizationStep = pathname === '/organizations'
  const isProjectStep = Boolean(routeOrganizationId) && !hasProject

  return null
}
