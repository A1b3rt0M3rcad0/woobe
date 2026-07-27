import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, FolderKanban, Plus } from 'lucide-react'

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
import { useOrganization } from '@/features/organizations/hooks'
import { useProjects, useProjectsForAccessManagement } from '@/features/projects/hooks'
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
  const {
    currentOrganization,
    selectOrganization,
    selectProject,
  } = useWorkspace()

  const { data: org, isLoading: orgLoading } = useOrganization(organizationId)
  const { data: projects, isLoading: projectsLoading, isError, error, refetch } = useProjects(organizationId)
  const { data: managedProjects } = useProjectsForAccessManagement(organizationId)
  const [query, setQuery] = useState('')

  const items = projects ?? []
  const canManageProjects = managedProjects !== undefined

  useEffect(() => {
    if (!org || currentOrganization?.id === org.id) return
    selectOrganization({ id: org.id, name: org.name, slug: org.slug })
  }, [currentOrganization, org, selectOrganization])

  const visibleProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return items

    return items.filter((project) => (
      project.name.toLowerCase().includes(normalizedQuery)
      || project.slug.toLowerCase().includes(normalizedQuery)
    ))
  }, [items, query])

  const startProjectSetup = () => {
    if (!organizationId || !canManageProjects) return
    navigate(`/organizations/${organizationId}/setup`)
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
          {canManageProjects && (
            <Button type="button" onClick={startProjectSetup}>
              <Plus className="mr-2 h-4 w-4" />
              Create Project
            </Button>
          )}
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
            title={canManageProjects ? 'Create the first Project' : 'No Project access yet'}
            description={canManageProjects
              ? 'Create the Project boundary, configure its first Agent and continue directly to the Playground.'
              : 'You belong to this Organization, but no Project has been shared with you yet.'}
            action={canManageProjects ? (
              <Button type="button" size="sm" onClick={startProjectSetup}>
                Start setup
              </Button>
            ) : undefined}
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
    </ResourcePage>
  )
}
