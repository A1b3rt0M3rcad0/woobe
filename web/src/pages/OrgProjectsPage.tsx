import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, FolderKanban, Plus } from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { Button } from '@/components/ui/Button'
import { CreateProjectDialog } from '@/components/forms/CreateProjectDialog'
import { useOrganization } from '@/features/organizations/hooks'
import { useCreateProject, useProjects } from '@/features/projects/hooks'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'

const SEARCH_THRESHOLD = 5

function getProjectInitial(name: string) {
  return name.trim()[0]?.toUpperCase() || 'P'
}

function formatDate(value?: string | null) {
  if (!value) return 'Not recorded'

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

export default function OrgProjectsPage() {
  const { organizationId } = useParams<{ organizationId: string }>()
  const navigate = useNavigate()
  const { selectProject } = useWorkspace()

  const { data: org, isLoading: orgLoading } = useOrganization(organizationId)
  const { data: projects, isLoading: projectsLoading, isError, error, refetch } = useProjects(organizationId)
  const createProject = useCreateProject(organizationId)

  const [showCreate, setShowCreate] = useState(false)
  const [query, setQuery] = useState('')

  const items = projects ?? []
  const visibleProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return items

    return items.filter((project) => (
      project.name.toLowerCase().includes(normalizedQuery)
      || project.slug.toLowerCase().includes(normalizedQuery)
    ))
  }, [items, query])

  const handleCreate = async (data: { name: string; slug: string }) => {
    if (!organizationId) return

    try {
      const isFirstProject = items.length === 0
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
      navigate(
        isFirstProject
          ? `/organizations/${organizationId}/projects/${project.id}/agents?create=1`
          : `/organizations/${organizationId}/projects/${project.id}`,
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create project')
    }
  }

  const handleSelect = (project: { id: string; organization_id: string; name: string; slug: string }) => {
    selectProject(project)
    navigate(`/organizations/${organizationId}/projects/${project.id}`)
  }

  if (!organizationId) return <ErrorState message="Organization not found" />
  if (!org && !orgLoading) return <ErrorState message="Organization not found" />

  const showSearch = items.length >= SEARCH_THRESHOLD
  const hasSearchMiss = Boolean(query.trim()) && visibleProjects.length === 0
  const resultCount = query.trim() ? `${visibleProjects.length} of ${items.length}` : items.length

  return (
    <ResourcePage
      title="Projects"
      description={org ? `Projects in ${org.name}.` : 'Select and operate a Project.'}
      action={(
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => navigate('/organizations')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Change Organization
          </Button>
          <Button type="button" onClick={() => setShowCreate(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create Project
          </Button>
        </div>
      )}
    >
      {showSearch && (
        <ResourceToolbar>
          <ResourceSearch
            value={query}
            onChange={setQuery}
            placeholder="Search Projects..."
            label="Search Projects"
          />
        </ResourceToolbar>
      )}

      <section>
        <ResourceSectionHeader
          title="Projects"
          description="Projects isolate Agents, Knowledge, Tools, credentials, runtime and observability."
          count={resultCount}
        />

        {orgLoading || projectsLoading ? (
          <LoadingState message="Loading Projects" variant="panel" layout="compact-cards" />
        ) : isError ? (
          <ErrorState error={error} onRetry={refetch} className="rounded-xl border border-border/80 bg-surface/40 py-10" />
        ) : items.length === 0 ? (
          <ResourceEmptyState
            icon={<FolderKanban className="h-4 w-4" />}
            title="Create your first Project"
            description="A Project isolates Agents, Knowledge, Tools, credentials, runtime and observability."
            action={(
              <Button type="button" size="sm" onClick={() => setShowCreate(true)}>
                Create Project
              </Button>
            )}
          />
        ) : hasSearchMiss ? (
          <ResourceEmptyState
            icon={<FolderKanban className="h-4 w-4" />}
            title="No Projects found"
            description="Adjust your search or clear the current term."
            action={(
              <Button type="button" size="sm" variant="outline" onClick={() => setQuery('')}>
                Clear search
              </Button>
            )}
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visibleProjects.map((project) => (
              <ResourceCard
                key={project.id}
                aria-label={`Open Project ${project.name}`}
                onClick={() => handleSelect(project)}
                icon={<span className="text-xs font-semibold">{getProjectInitial(project.name)}</span>}
                title={project.name}
                subtitle={`/${project.slug}`}
                footer={`Updated · ${formatDate(project.updated_at || project.created_at)}`}
              />
            ))}
          </div>
        )}
      </section>

      <CreateProjectDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={handleCreate}
        loading={createProject.isPending}
      />
    </ResourcePage>
  )
}
