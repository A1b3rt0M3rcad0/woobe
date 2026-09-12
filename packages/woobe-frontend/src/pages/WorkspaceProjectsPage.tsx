import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AlertCircle, ArrowLeft, Building2, ChevronRight, FolderKanban, Plus, Search, X } from 'lucide-react'
import { Badge, Button, Card, Input } from '@woobe/ui'
import { toast } from 'sonner'

import { CreateProjectDialog } from '@/components/forms/CreateProjectDialog'
import { useWorkspaceDetail } from '@/features/workspaces/hooks'
import { useCreateProject, useProjects } from '@/features/projects/hooks'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import type { Project } from '@/features/projects/types'

const SEARCH_THRESHOLD = 5

function getProjectInitial(name: string) {
  return name.trim()[0]?.toUpperCase() || 'P'
}

function formatDate(value?: string | null) {
  if (!value) return 'Not recorded'
  try {
    return new Intl.DateTimeFormat('en-US', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value))
  } catch {
    return 'Invalid date'
  }
}

function accessLabel(project: Project) {
  return project.access_source === 'workspace_owner'
    ? 'Workspace Owner · implicit access'
    : `${project.workspace_role ?? 'Member'} · granted Project access`
}

function SectionHeading({
  title,
  description,
  count,
}: {
  title: string
  description?: string
  count?: ReactNode
}) {
  return (
    <div className="mb-3">
      <div className="flex items-center gap-2.5">
        <span className="h-[5px] w-[5px] shrink-0 bg-primary" aria-hidden="true" />
        <h2 className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-slate-100">{title}</h2>
        <span className="h-px min-w-6 flex-1 bg-border" />
        {count !== undefined && (
          <span className="shrink-0 font-mono text-[9px] text-muted-foreground">{count}</span>
        )}
      </div>
      {description && (
        <p className="mt-1.5 pl-[15px] font-mono text-[9px] leading-4 text-muted-foreground">{description}</p>
      )}
    </div>
  )
}

function ProjectSearch({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="relative w-full max-w-sm">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
      <Input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && value) {
            event.preventDefault()
            onChange('')
          }
        }}
        placeholder="Search Projects..."
        aria-label="Search Projects"
        className="pl-9 pr-9 font-mono text-[10px]"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear search"
          className="absolute right-1 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-technical text-muted-foreground transition-colors hover:bg-accent hover:text-slate-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}

function ProjectCard({ project, onSelect }: { project: Project; onSelect: () => void }) {
  const implicitAccess = project.access_source === 'workspace_owner'

  return (
    <button
      type="button"
      aria-label={`Open Project ${project.name}`}
      onClick={onSelect}
      className="group flex min-h-[136px] w-full flex-col rounded-container border border-border bg-surface text-left transition-colors hover:border-slate-600 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
    >
      <span className="flex flex-1 items-start justify-between gap-4 p-4">
        <span className="flex min-w-0 items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-border bg-control font-mono text-[10px] font-bold text-primary-light">
            {getProjectInitial(project.name)}
          </span>
          <span className="min-w-0">
            <span className="block truncate font-mono text-xs font-bold tracking-[0.01em] text-slate-50">{project.name}</span>
            <span className="mt-1 block truncate font-mono text-[9px] text-muted-foreground">/{project.slug}</span>
            <span className="mt-3 block font-mono text-[8px] uppercase tracking-[0.08em] text-muted">
              {accessLabel(project)}
            </span>
          </span>
        </span>
        <Badge
          variant={implicitAccess ? 'default' : 'outline'}
          className="shrink-0 font-mono text-[8px] uppercase tracking-[0.08em]"
        >
          {implicitAccess ? 'implicit' : 'assigned'}
        </Badge>
      </span>
      <span className="flex w-full items-center justify-between gap-3 border-t border-border bg-control/35 px-4 py-2.5">
        <span className="truncate font-mono text-[9px] text-muted-foreground">
          Updated · {formatDate(project.updated_at || project.created_at)}
        </span>
        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary-light" />
      </span>
    </button>
  )
}

function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: ReactNode
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <Card className="border-dashed px-6 py-10 text-center">
      <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-control border border-border bg-control text-muted-foreground">
        {icon}
      </div>
      <h3 className="mt-3 font-mono text-[11px] font-bold text-slate-100">{title}</h3>
      <p className="mx-auto mt-1.5 max-w-lg font-mono text-[9px] leading-4 text-muted-foreground">{description}</p>
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </Card>
  )
}

function ProjectLoadingGrid({ count = 3 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: count }).map((_, index) => (
        <Card key={index} className="min-h-[136px] animate-pulse p-4">
          <div className="flex items-start gap-3">
            <div className="h-8 w-8 rounded-control bg-accent" />
            <div className="flex-1 space-y-2">
              <div className="h-2.5 w-2/3 bg-accent" />
              <div className="h-2 w-1/2 bg-accent/80" />
              <div className="mt-4 h-2 w-1/3 bg-accent/70" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}

export default function WorkspaceProjectsPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const navigate = useNavigate()
  const { currentWorkspace, selectWorkspace, selectProject } = useWorkspace()
  const { data: workspace, isLoading: workspaceLoading } = useWorkspaceDetail(workspaceId)
  const { data: projects, isLoading: projectsLoading, isError, error, refetch } = useProjects(workspaceId)
  const createProject = useCreateProject(workspaceId)
  const [query, setQuery] = useState('')
  const [showCreate, setShowCreate] = useState(false)

  const items = projects ?? []
  const currentRole = currentWorkspace?.membership_role
  const canManageProjects = currentRole === 'owner' || currentRole === 'admin'

  useEffect(() => {
    if (!workspace || currentWorkspace?.id === workspace.id) return
    selectWorkspace({ id: workspace.id, name: workspace.name, slug: workspace.slug })
  }, [currentWorkspace, workspace, selectWorkspace])

  const visibleProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return items
    return items.filter((project) => `${project.name} ${project.slug} ${project.workspace_role ?? ''}`.toLowerCase().includes(normalizedQuery))
  }, [items, query])

  const handleCreate = async (data: { name: string; slug: string }) => {
    if (!workspaceId) return
    try {
      const project = await createProject.mutateAsync({
        workspace_id: workspaceId,
        name: data.name,
        slug: data.slug,
      })
      toast.success('Project created')
      setShowCreate(false)
      selectProject(project)
      navigate(`/workspaces/${workspaceId}/projects/${project.id}`)
    } catch (createError) {
      toast.error(createError instanceof Error ? createError.message : 'Failed to create Project')
    }
  }

  const handleSelect = (project: Project) => {
    selectProject(project)
    navigate(`/workspaces/${workspaceId}/projects/${project.id}`)
  }

  if (!workspaceId) {
    return (
      <Card className="border-error/30 bg-error/[0.05] px-6 py-10 text-center">
        <AlertCircle className="mx-auto h-5 w-5 text-red-300" />
        <h3 className="mt-3 font-mono text-[11px] font-bold text-slate-100">Workspace not found</h3>
      </Card>
    )
  }

  if (!workspace && !workspaceLoading) {
    return (
      <Card className="border-error/30 bg-error/[0.05] px-6 py-10 text-center">
        <AlertCircle className="mx-auto h-5 w-5 text-red-300" />
        <h3 className="mt-3 font-mono text-[11px] font-bold text-slate-100">Workspace not found</h3>
      </Card>
    )
  }

  const showSearch = items.length >= SEARCH_THRESHOLD
  const hasSearchMiss = Boolean(query.trim()) && visibleProjects.length === 0
  const resultCount = query.trim() ? `${visibleProjects.length} of ${items.length}` : items.length
  const errorMessage = error instanceof Error ? error.message : 'Failed to load Projects'

  return (
    <div className="mx-auto w-full max-w-[1540px]">
      <header className="flex flex-col gap-4 border-b border-border pb-4 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-7 w-8 shrink-0 items-center border-r border-border text-primary-light">
            <FolderKanban className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h1 className="font-mono text-base font-bold tracking-[0.01em] text-slate-50">Projects</h1>
            <p className="mt-0.5 truncate font-mono text-[9px] text-muted-foreground">
              {workspace ? `Projects in ${workspace.name}.` : 'Select and operate a Project.'}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => navigate('/workspaces')}>
            <ArrowLeft className="h-3.5 w-3.5" />
            Change Workspace
          </Button>
          <Button type="button" variant="outline" onClick={() => navigate(`/workspaces/${workspaceId}/settings`)}>
            <Building2 className="h-3.5 w-3.5" />
            Workspace
          </Button>
          {canManageProjects && (
            <Button type="button" onClick={() => setShowCreate(true)}>
              <Plus className="h-3.5 w-3.5" />
              Create Project
            </Button>
          )}
        </div>
      </header>

      <div className="pt-5">
        <section>
          <SectionHeading
            title="Projects"
            description="Projects isolate Agents, Knowledge, Tools, credentials, runtime and observability."
            count={resultCount}
          />

          {showSearch && (
            <div className="mb-3 flex justify-end">
              <ProjectSearch value={query} onChange={setQuery} />
            </div>
          )}

          {workspaceLoading || projectsLoading ? (
            <ProjectLoadingGrid />
          ) : isError ? (
            <Card className="border-error/30 bg-error/[0.05] px-6 py-10 text-center">
              <AlertCircle className="mx-auto h-5 w-5 text-red-300" />
              <h3 className="mt-3 font-mono text-[11px] font-bold text-slate-100">Unable to load Projects</h3>
              <p className="mx-auto mt-1.5 max-w-lg font-mono text-[9px] leading-4 text-red-200/80">{errorMessage}</p>
              <div className="mt-4 flex justify-center">
                <Button type="button" size="sm" variant="outline" onClick={() => refetch()}>Try again</Button>
              </div>
            </Card>
          ) : items.length === 0 ? (
            <EmptyState
              icon={<FolderKanban className="h-3.5 w-3.5" />}
              title={canManageProjects ? 'Create the first Project' : 'No Project access yet'}
              description={canManageProjects
                ? 'Create the Project boundary and start configuring its runtime assets.'
                : 'You belong to this Workspace, but no Project has been shared with you yet.'}
              action={canManageProjects
                ? <Button type="button" size="sm" onClick={() => setShowCreate(true)}>Create Project</Button>
                : undefined}
            />
          ) : hasSearchMiss ? (
            <EmptyState
              icon={<Search className="h-3.5 w-3.5" />}
              title="No Projects found"
              description="Adjust your search or clear the current term."
              action={<Button type="button" size="sm" variant="outline" onClick={() => setQuery('')}>Clear search</Button>}
            />
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {visibleProjects.map((project) => (
                <ProjectCard key={project.id} project={project} onSelect={() => handleSelect(project)} />
              ))}
            </div>
          )}
        </section>
      </div>

      <CreateProjectDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={handleCreate}
        loading={createProject.isPending}
        firstProject={items.length === 0}
      />
    </div>
  )
}
