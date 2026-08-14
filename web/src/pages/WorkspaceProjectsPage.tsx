import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Building2, FolderKanban, Plus } from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard, ResourcePill } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { Button } from '@/components/ui/Button'
import { useWorkspaceDetail } from '@/features/workspaces/hooks'
import { useProjects } from '@/features/projects/hooks'
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

export default function WorkspaceProjectsPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const navigate = useNavigate()
  const { currentWorkspace, selectWorkspace, selectProject } = useWorkspace()
  const { data: workspace, isLoading: workspaceLoading } = useWorkspaceDetail(workspaceId)
  const { data: projects, isLoading: projectsLoading, isError, error, refetch } = useProjects(workspaceId)
  const [query, setQuery] = useState('')

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

  const startProjectSetup = () => {
    if (workspaceId && canManageProjects) navigate(`/workspaces/${workspaceId}/setup`)
  }

  const handleSelect = (project: Project) => {
    selectProject(project)
    navigate(`/workspaces/${workspaceId}/projects/${project.id}`)
  }

  if (!workspaceId) return <ErrorState message="Workspace not found" />
  if (!workspace && !workspaceLoading) return <ErrorState message="Workspace not found" />

  const showSearch = items.length >= SEARCH_THRESHOLD
  const hasSearchMiss = Boolean(query.trim()) && visibleProjects.length === 0
  const resultCount = query.trim() ? `${visibleProjects.length} of ${items.length}` : items.length

  return (
    <ResourcePage
      title="Projects"
      description={workspace ? `Projects in ${workspace.name}.` : 'Select and operate a Project.'}
      action={(
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => navigate('/workspaces')}><ArrowLeft className="mr-2 h-4 w-4" />Change Workspace</Button>
          <Button type="button" variant="outline" onClick={() => navigate(`/workspaces/${workspaceId}/settings`)}><Building2 className="mr-2 h-4 w-4" />Workspace</Button>
          {canManageProjects && <Button type="button" onClick={startProjectSetup}><Plus className="mr-2 h-4 w-4" />Create Project</Button>}
        </div>
      )}
    >
      {showSearch && <ResourceToolbar><ResourceSearch value={query} onChange={setQuery} placeholder="Search Projects..." label="Search Projects" /></ResourceToolbar>}
      <section>
        <ResourceSectionHeader title="Projects" description="Projects isolate Agents, Knowledge, Tools, credentials, runtime and observability." count={resultCount} />
        {workspaceLoading || projectsLoading ? (
          <LoadingState message="Loading Projects" variant="panel" layout="compact-cards" />
        ) : isError ? (
          <ErrorState error={error} onRetry={refetch} className="rounded-xl border border-border/80 bg-surface/40 py-10" />
        ) : items.length === 0 ? (
          <ResourceEmptyState
            icon={<FolderKanban className="h-4 w-4" />}
            title={canManageProjects ? 'Create the first Project' : 'No Project access yet'}
            description={canManageProjects ? 'Create the Project boundary, configure its first Agent and continue directly to the Playground.' : 'You belong to this Workspace, but no Project has been shared with you yet.'}
            action={canManageProjects ? <Button type="button" size="sm" onClick={startProjectSetup}>Start setup</Button> : undefined}
          />
        ) : hasSearchMiss ? (
          <ResourceEmptyState icon={<FolderKanban className="h-4 w-4" />} title="No Projects found" description="Adjust your search or clear the current term." action={<Button type="button" size="sm" variant="outline" onClick={() => setQuery('')}>Clear search</Button>} />
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
                status={<ResourcePill tone={project.access_source === 'workspace_owner' ? 'primary' : 'default'}>{project.access_source === 'workspace_owner' ? 'IMPLICIT' : 'ASSIGNED'}</ResourcePill>}
                metadata={<ResourcePill>{accessLabel(project)}</ResourcePill>}
                footer={`Updated · ${formatDate(project.updated_at || project.created_at)}`}
              />
            ))}
          </div>
        )}
      </section>
    </ResourcePage>
  )
}
