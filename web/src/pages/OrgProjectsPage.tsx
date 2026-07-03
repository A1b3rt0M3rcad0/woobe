import { useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { useProjects, useCreateProject } from '@/features/projects/hooks'
import { useOrganization } from '@/features/organizations/hooks'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { CreateProjectDialog } from '@/components/forms/CreateProjectDialog'
import { ArrowLeft, ArrowRight, Building2, Plus, Search } from 'lucide-react'
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
  const { selectProject } = useWorkspace()

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

  const hasSearchMiss = query.trim().length > 0 && visibleProjects.length === 0

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Select your project</h1>
        <p className="mt-2 text-sm text-muted">Projects contain agents, knowledge, tools and runtime configurations.</p>
      </div>

      <Card className="border-primary/25 bg-primary/10">
        <CardContent className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-primary/35 bg-background text-primary-light">
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-primary-light">Organization</p>
              <h2 className="mt-1 text-base font-semibold text-white">{org.name}</h2>
              <p className="mt-1 font-mono text-sm text-muted">/{org.slug}</p>
            </div>
          </div>
          <Button
            className="w-full md:w-auto"
            size="sm"
            variant="outline"
            onClick={() => navigate('/organizations')}
          >
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
            Change organization
          </Button>
        </CardContent>
      </Card>

      <div className="relative max-w-3xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search projects..."
          className="h-11 pl-9"
        />
      </div>

      {hasSearchMiss && (
        <div className="rounded-xl border border-border/80 bg-surface/50 px-5 py-4">
          <h2 className="text-sm font-semibold text-white">No projects found</h2>
          <p className="mt-1 text-sm text-muted">Create a new project or adjust the search term.</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="group flex min-h-[260px] flex-col items-center justify-center rounded-xl border border-dashed border-primary/40 bg-surface/35 p-6 text-center transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/60 hover:bg-primary/5 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          <span className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/50 bg-primary/10 text-primary-light transition-colors duration-200 group-hover:bg-primary/15">
            <Plus className="h-6 w-6" />
          </span>
          <span className="mt-5 text-base font-semibold text-white">New project</span>
          <span className="mt-2 max-w-[180px] text-sm leading-6 text-muted">Create a project in {org.name}</span>
        </button>

        {visibleProjects.map((p) => {
          const status = p.status || 'Active'
          const recentDate = p.updated_at || p.created_at

          return (
            <button
              key={p.id}
              type="button"
              aria-label={`Open project ${p.name}`}
              onClick={() => handleSelect(p)}
              className="group flex min-h-[260px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              <span className="flex items-start justify-between gap-3">
                <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-sm font-semibold text-primary-light shadow-sm transition-colors duration-200 group-hover:border-primary/30 group-hover:bg-primary/10">
                  {getProjectInitial(p.name)}
                </span>
                <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${getStatusClass(p.status)}`}>
                  {status}
                </span>
              </span>

              <span className="mt-6 block min-w-0">
                <span className="block truncate text-base font-semibold text-white">{p.name}</span>
                <span className="mt-1 block truncate font-mono text-sm text-muted">/{p.slug}</span>
              </span>

              <span className="my-5 block h-px bg-border/80" />

              <span className="block space-y-3 text-sm">
                <span className="block">
                  <span className="block text-xs text-muted">Organization</span>
                  <span className="mt-1 block truncate font-medium text-white">{org.name}</span>
                </span>
                <span className="block">
                  <span className="block text-xs text-muted">Updated</span>
                  <span className="mt-1 block truncate font-medium text-white">{formatDate(recentDate)}</span>
                </span>
              </span>

              <span className="mt-auto flex w-full items-center justify-between pt-5 text-sm font-medium text-primary-light transition-colors duration-200 group-hover:text-white">
                Open project
                <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
              </span>
            </button>
          )
        })}
      </div>

      <CreateProjectDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={handleCreate}
        loading={createProject.isPending}
      />
    </div>
  )
}
