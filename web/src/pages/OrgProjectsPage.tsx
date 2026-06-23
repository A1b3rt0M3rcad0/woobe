import { useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { useProjects, useCreateProject } from '@/features/projects/hooks'
import { useOrganization } from '@/features/organizations/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { CreateProjectDialog } from '@/components/forms/CreateProjectDialog'
import { Activity, ArrowRight, Building2, CheckCircle2, Clock3, FolderKanban, Plus, Search, Settings } from 'lucide-react'
import { toast } from 'sonner'

function getProjectInitial(name: string) {
  return name.trim()[0]?.toUpperCase() || 'P'
}

function formatDate(value?: string | null) {
  if (!value) return 'No recent date'

  try {
    return new Intl.DateTimeFormat('en-US', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }).format(new Date(value))
  } catch {
    return 'Invalid date'
  }
}

function getStatusClass(status?: string) {
  const normalized = status?.toLowerCase() || ''

  if (normalized.includes('concl') || normalized.includes('done') || normalized.includes('complete')) {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
  }

  if (normalized.includes('planej') || normalized.includes('plan')) {
    return 'border-amber-500/30 bg-amber-500/10 text-amber-300'
  }

  if (normalized.includes('revis') || normalized.includes('review')) {
    return 'border-violet-500/30 bg-violet-500/10 text-violet-300'
  }

  return 'border-primary/35 bg-primary/10 text-primary-light'
}

export default function OrgProjectsPage() {
  const { organizationId } = useParams<{ organizationId: string }>()
  const navigate = useNavigate()
  const { selectProject, currentProject } = useWorkspace()

  const { data: org, isLoading: orgLoading } = useOrganization(organizationId)
  const { data: projects, isLoading: projectsLoading, isError, error, refetch } = useProjects(organizationId)
  const createProject = useCreateProject(organizationId)

  const [showCreate, setShowCreate] = useState(false)
  const [query, setQuery] = useState('')

  const visibleProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    const items = projects ?? []

    if (!normalizedQuery) return items

    return items.filter((project) => (
      project.name.toLowerCase().includes(normalizedQuery)
      || project.slug.toLowerCase().includes(normalizedQuery)
      || project.status?.toLowerCase().includes(normalizedQuery)
    ))
  }, [projects, query])

  const statusSummary = useMemo(() => {
    const items = projects ?? []
    const withStatus = items.filter((project) => Boolean(project.status)).length
    const updated = items.filter((project) => Boolean(project.updated_at || project.created_at)).length

    return { withStatus, updated }
  }, [projects])

  const handleCreate = async (data: { name: string; slug: string }) => {
    if (!organizationId) return
    try {
      const project = await createProject.mutateAsync({
        organization_id: organizationId,
        ...data,
      })
      toast.success('Project created')
      setShowCreate(false)
      selectProject({
        id: project.id,
        organization_id: project.organization_id,
        name: project.name,
        slug: project.slug,
      })
      navigate(`/organizations/${organizationId}/projects/${project.id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create project')
    }
  }

  const handleSelect = (p: { id: string; organization_id: string; name: string; slug: string }) => {
    selectProject(p)
    navigate(`/organizations/${organizationId}/projects/${p.id}`)
  }

  if (orgLoading || projectsLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />
  if (!org) return <ErrorState message="Organization not found" />

  const projectCount = projects?.length ?? 0
  const hasProjects = projectCount > 0

  return (
    <div className="space-y-6">
      <PageHeader
        title="Select your project"
        description={
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            <span>Projects contain your agents, knowledge, tools and configurations.</span>
            <span className="hidden text-border sm:inline">•</span>
            <span>{projectCount} {projectCount === 1 ? 'project' : 'projects'} in this organization</span>
          </div>
        }
        actions={
          <>
            <Button variant="outline" onClick={() => navigate(`/organizations/${organizationId}/settings`)}>
              <Settings className="mr-2 h-4 w-4" />
              Organization Settings
            </Button>
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="mr-2 h-4 w-4" />
              New Project
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <Card className="overflow-hidden border-border/80 bg-surface/80">
          <CardContent className="flex flex-col gap-4 p-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-primary/30 bg-primary/10 text-primary-light">
                <Building2 className="h-6 w-6" />
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary-light">Organization</p>
                <h2 className="mt-2 text-lg font-semibold text-white">{org.name}</h2>
                <p className="mt-1 max-w-2xl text-sm text-muted">
                  Search projects before opening the operational workspace.
                </p>
              </div>
            </div>
            <div className="relative w-full md:max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search projects..."
                className="pl-9"
              />
            </div>
          </CardContent>
        </Card>

        <Card className="border-primary/20 bg-primary/10">
          <CardContent className="grid grid-cols-2 gap-3 p-4">
            <div className="rounded-xl border border-border bg-background/70 p-3">
              <div className="flex items-center gap-2 text-xs text-muted">
                <Activity className="h-3.5 w-3.5 text-primary-light" />
                With status
              </div>
              <p className="mt-2 text-2xl font-semibold text-white">{statusSummary.withStatus}</p>
            </div>
            <div className="rounded-xl border border-border bg-background/70 p-3">
              <div className="flex items-center gap-2 text-xs text-muted">
                <Clock3 className="h-3.5 w-3.5 text-primary-light" />
                Dated
              </div>
              <p className="mt-2 text-2xl font-semibold text-white">{statusSummary.updated}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {!hasProjects ? (
        <EmptyState
          icon={<FolderKanban className="h-12 w-12" />}
          title="No projects yet"
          description="Create a project to organize agents, knowledge and tools."
          action={
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Project
            </Button>
          }
        />
      ) : visibleProjects.length === 0 ? (
        <Card className="border-dashed border-border bg-surface/60">
          <CardContent className="flex flex-col items-center justify-center px-6 py-12 text-center">
            <Search className="h-10 w-10 text-muted" />
            <h3 className="mt-4 text-base font-semibold text-white">No projects found</h3>
            <p className="mt-1 max-w-md text-sm text-muted">Adjust the search by name, slug or status.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visibleProjects.map((p) => {
            const isSelected = p.id === currentProject?.id
            const status = p.status || 'Active'
            const recentDate = p.updated_at || p.created_at

            return (
              <Card
                key={p.id}
                className={`group relative overflow-hidden transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5 ${isSelected ? 'border-primary/60 bg-primary/10 ring-1 ring-primary/30' : 'border-border bg-surface'}`}
              >
                <CardHeader className="pb-4">
                  <div className="mb-4 flex items-start justify-between gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-primary/25 bg-background text-sm font-semibold text-primary-light shadow-sm">
                      {getProjectInitial(p.name)}
                    </div>
                    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${getStatusClass(p.status)}`}>
                      {isSelected && <CheckCircle2 className="h-3 w-3" />}
                      {status}
                    </span>
                  </div>

                  <CardTitle className="flex items-center gap-2 text-white">
                    <FolderKanban className="h-4 w-4 text-primary" />
                    {p.name}
                  </CardTitle>
                  <CardDescription className="font-mono">/{p.slug}</CardDescription>
                </CardHeader>

                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 rounded-lg border border-border/70 bg-background/70 p-3">
                    <div>
                      <p className="text-xs text-muted">Organization</p>
                      <p className="mt-1 truncate text-sm font-medium text-white">{org.name}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted">Updated</p>
                      <p className="mt-1 truncate text-sm font-medium text-white">{formatDate(recentDate)}</p>
                    </div>
                  </div>

                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Button className="flex-1" size="sm" variant={isSelected ? 'default' : 'outline'} onClick={() => handleSelect(p)}>
                      Open project
                      <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => navigate(`/organizations/${organizationId}/projects/${p.id}/settings`)}>
                      <Settings className="mr-1.5 h-3.5 w-3.5" />
                      Settings
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      <CreateProjectDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={handleCreate}
        loading={createProject.isPending}
      />
    </div>
  )
}
