import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Boxes, FolderKanban, Plus } from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard, ResourcePill } from '@/components/common/OperationalResourceCard'
import { ResourceEmptyState, ResourcePage, ResourceSearch, ResourceSectionHeader, ResourceToolbar } from '@/components/common/ResourcePage'
import { Button } from '@/components/ui/Button'
import { useProjects } from '@/features/projects/hooks'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { useQuery } from '@tanstack/react-query'
import { getWorkspace } from '@/features/workspaces/api'
import type { Project } from '@/features/projects/types'

const SEARCH_THRESHOLD = 5

export default function WorkspaceProjectsPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const navigate = useNavigate()
  const { currentWorkspace, selectWorkspace, selectProject } = useWorkspace()
  const workspaceQuery = useQuery({ queryKey: ['workspace', workspaceId], queryFn: () => getWorkspace(workspaceId!), enabled: Boolean(workspaceId) })
  const projectsQuery = useProjects(workspaceId)
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (!workspaceQuery.data || currentWorkspace?.id === workspaceQuery.data.id) return
    selectWorkspace(workspaceQuery.data)
  }, [currentWorkspace?.id, selectWorkspace, workspaceQuery.data])

  if (!workspaceId) return <ErrorState message="Workspace not found" />
  if (workspaceQuery.isLoading || projectsQuery.isLoading) return <LoadingState message="Loading Projects" variant="panel" layout="compact-cards" />
  if (workspaceQuery.isError) return <ErrorState error={workspaceQuery.error} onRetry={workspaceQuery.refetch} />
  if (projectsQuery.isError) return <ErrorState error={projectsQuery.error} onRetry={projectsQuery.refetch} />
  const workspace = workspaceQuery.data
  if (!workspace) return <ErrorState message="Workspace not found" />

  const projects = projectsQuery.data ?? []
  const visible = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return projects
    return projects.filter((project) => `${project.name} ${project.slug}`.toLowerCase().includes(term))
  }, [projects, query])
  const canManage = Boolean(workspace.can_manage)
  const openProject = (project: Project) => {
    selectProject(project)
    navigate(`/workspaces/${workspaceId}/projects/${project.id}`)
  }

  return (
    <ResourcePage
      title="Projects"
      description={`Projects in ${workspace.name}.`}
      action={<div className="flex gap-2">
        <Button variant="outline" onClick={() => navigate('/workspaces')}><ArrowLeft className="mr-2 h-4 w-4" />Change Workspace</Button>
        <Button variant="outline" onClick={() => navigate(`/workspaces/${workspaceId}/settings`)}><Boxes className="mr-2 h-4 w-4" />Workspace</Button>
        {canManage && <Button onClick={() => navigate(`/workspaces/${workspaceId}/setup`)}><Plus className="mr-2 h-4 w-4" />Create Project</Button>}
      </div>}
    >
      {projects.length >= SEARCH_THRESHOLD && <ResourceToolbar><ResourceSearch value={query} onChange={setQuery} placeholder="Search Projects..." label="Search Projects" /></ResourceToolbar>}
      <section>
        <ResourceSectionHeader title="Projects" description="Projects isolate Agents, Knowledge, Tools, runtime and observability." count={visible.length} />
        {visible.length === 0 ? (
          <ResourceEmptyState icon={<FolderKanban className="h-4 w-4" />} title={canManage ? 'Create the first Project' : 'No Project access yet'} description={canManage ? 'Create a Project and configure its first Agent.' : 'The Instance admin has not granted Project access yet.'} action={canManage ? <Button size="sm" onClick={() => navigate(`/workspaces/${workspaceId}/setup`)}>Start setup</Button> : undefined} />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visible.map((project) => (
              <ResourceCard
                key={project.id}
                onClick={() => openProject(project)}
                icon={<FolderKanban className="h-4 w-4" />}
                title={project.name}
                subtitle={`/${project.slug}`}
                status={<ResourcePill tone={project.access_source === 'instance_admin' ? 'primary' : 'default'}>{project.access_source === 'instance_admin' ? 'ADMIN' : 'ASSIGNED'}</ResourcePill>}
                footer="Open Project"
              />
            ))}
          </div>
        )}
      </section>
    </ResourcePage>
  )
}
