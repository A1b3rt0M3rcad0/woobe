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

  const openOrganization = (organization: { id: string; name: string; slug: string }) => {
    selectOrganization(organization)
    navigate(`/organizations/${organization.id}/projects`)
  }

  const openProject = (project: { id: string; organization_id: string; name: string; slug: string }) => {
    selectProject(project)
    navigate(`/organizations/${project.organization_id}/projects/${project.id}`)
  }

  const content = (
    <div className="flex h-full flex-col border-border bg-surface">
      <div className="border-b border-border p-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Play className="h-4 w-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">Workspace setup</p>
            <p className="text-xs text-muted">Choose where you want to work.</p>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-4 p-3">
          <section className={cn('rounded-xl border p-3', isOrganizationStep ? 'border-primary/50 bg-primary/10' : 'border-border bg-background/50')}>
            <div className="mb-3 flex items-center gap-2">
              <StepBadge done={hasOrganization} active={isOrganizationStep} />
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">Step 1</p>
                <p className="text-sm font-semibold text-white">Organization</p>
              </div>
            </div>
            <div className="space-y-1">
              {organizations.slice(0, compact ? 3 : 8).map((organization) => {
                const active = organization.id === selectedOrganization?.id
                return (
                  <button
                    key={organization.id}
                    className={cn('flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors', active ? 'bg-primary/15 text-white' : 'text-muted hover:bg-accent hover:text-white')}
                    onClick={() => openOrganization(organization)}
                  >
                    <Building2 className="h-3.5 w-3.5 shrink-0" />
                    <span className="min-w-0 flex-1 truncate">{organization.name}</span>
                  </button>
                )
              })}
              {organizations.length === 0 && <p className="px-2 py-2 text-xs text-muted">Create an organization to start.</p>}
            </div>
            <Button className="mt-3 w-full" size="sm" variant="outline" onClick={() => navigate('/organizations')}>
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              New organization
            </Button>
          </section>

          <section className={cn('rounded-xl border p-3', isProjectStep ? 'border-primary/50 bg-primary/10' : 'border-border bg-background/50', !hasOrganization && 'opacity-60')}>
            <div className="mb-3 flex items-center gap-2">
              <StepBadge done={hasProject} active={isProjectStep} blocked={!hasOrganization} />
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">Step 2</p>
                <p className="text-sm font-semibold text-white">Project</p>
              </div>
            </div>
            {!hasOrganization ? (
              <p className="text-xs text-muted">Select an organization before choosing a project.</p>
            ) : (
              <>
                <div className="space-y-1">
                  {projects.slice(0, compact ? 3 : 8).map((project) => {
                    const active = project.id === currentProject?.id
                    return (
                      <button key={project.id} className={cn('flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors', active ? 'bg-primary/15 text-white' : 'text-muted hover:bg-accent hover:text-white')} onClick={() => openProject(project)}>
                        <FolderKanban className="h-3.5 w-3.5 shrink-0" />
                        <span className="min-w-0 flex-1 truncate">{project.name}</span>
                      </button>
                    )
                  })}
                  {projects.length === 0 && <p className="px-2 py-2 text-xs text-muted">Create a project inside this organization.</p>}
                </div>
                <Button className="mt-3 w-full" size="sm" variant="outline" onClick={() => navigate(`/organizations/${selectedOrganization?.id}/projects`)}>
                  <Plus className="mr-1.5 h-3.5 w-3.5" />
                  New project
                </Button>
              </>
            )}
          </section>

          <section className={cn('rounded-xl border border-border bg-background/50 p-3', !hasProject && 'opacity-60')}>
            <div className="mb-3 flex items-center gap-2">
              <StepBadge active={hasProject} blocked={!hasProject} />
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">Step 3</p>
                <p className="text-sm font-semibold text-white">Build</p>
              </div>
            </div>
            <p className="text-xs text-muted">{hasProject ? 'Open the project workspace and start building agents.' : 'Select a project to unlock agents, knowledge, tools and API keys.'}</p>
            <Button className="mt-3 w-full" size="sm" disabled={!currentOrganization || !currentProject} onClick={() => currentOrganization && currentProject && navigate(`/organizations/${currentOrganization.id}/projects/${currentProject.id}`)}>
              <LayoutDashboard className="mr-1.5 h-3.5 w-3.5" />
              Open workspace
            </Button>
          </section>
        </div>
      </ScrollArea>

      {selectedOrganization && (
        <div className="border-t border-border p-3">
          <Button className="w-full" size="sm" variant="ghost" onClick={() => navigate(`/organizations/${selectedOrganization.id}/settings`)}>
            <Settings className="mr-1.5 h-3.5 w-3.5" />
            Organization settings
          </Button>
        </div>
      )}
    </div>
  )

  if (compact) return <div className="border-b border-border bg-surface lg:hidden">{content}</div>
  return <aside className="flex w-72 shrink-0 flex-col border-r border-border bg-surface">{content}</aside>
}
