import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { FirstRunAgentSetup } from '@/features/first-run/components/FirstRunAgentSetup'
import { FirstRunProjectStep } from '@/features/first-run/components/FirstRunProjectStep'
import { FirstRunShell } from '@/features/first-run/components/FirstRunShell'
import type { Agent } from '@/features/agents/types'
import { useWorkspaceDetail } from '@/features/workspaces/hooks'
import { useCreateProject, useProject } from '@/features/projects/hooks'
import { createProjectSchema, type CreateProjectFormData } from '@/features/projects/schemas'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { slugify } from '@/lib/slug'

export function firstRunProjectSetupPath(workspaceId: string, projectId: string) {
  return `/workspaces/${workspaceId}/projects/${projectId}/setup`
}

export function firstRunPlaygroundPath(workspaceId: string, projectId: string, agentId: string) {
  return `/workspaces/${workspaceId}/projects/${projectId}/agents/${agentId}/playground?firstRun=1`
}

export function firstRunExitPath(workspaceId: string, projectId?: string) {
  return projectId
    ? `/workspaces/${workspaceId}/projects/${projectId}/agents`
    : `/workspaces/${workspaceId}/projects`
}

export default function FirstRunSetupPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId?: string }>()
  const navigate = useNavigate()
  const {
    currentWorkspace,
    currentProject,
    selectWorkspace,
    selectProject,
  } = useWorkspace()
  const workspaceQuery = useWorkspaceDetail(workspaceId)
  const projectQuery = useProject(projectId)
  const createProject = useCreateProject(workspaceId)
  const form = useForm<CreateProjectFormData>({
    resolver: zodResolver(createProjectSchema),
    defaultValues: { name: '' },
  })

  const workspace = workspaceQuery.data
  const project = projectQuery.data || (currentProject?.id === projectId ? currentProject : null)

  useEffect(() => {
    if (!workspace || currentWorkspace?.id === workspace.id) return
    selectWorkspace({
      id: workspace.id,
      name: workspace.name,
      slug: workspace.slug,
    })
  }, [currentWorkspace, workspace, selectWorkspace])

  useEffect(() => {
    if (!projectQuery.data || currentProject?.id === projectQuery.data.id) return
    selectProject({
      id: projectQuery.data.id,
      workspace_id: projectQuery.data.workspace_id,
      name: projectQuery.data.name,
      slug: projectQuery.data.slug,
    })
  }, [currentProject, projectQuery.data, selectProject])

  if (!workspaceId) return <ErrorState message="Workspace not found" />
  if (workspaceQuery.isLoading) return <LoadingState message="Opening first-run setup" />
  if (workspaceQuery.isError) return <ErrorState error={workspaceQuery.error} onRetry={workspaceQuery.refetch} />
  if (!workspace) return <ErrorState message="Workspace not found" />
  if (projectId && projectQuery.isLoading && !project) return <LoadingState message="Opening Project setup" />
  if (projectId && projectQuery.isError && !project) return <ErrorState error={projectQuery.error} onRetry={projectQuery.refetch} />

  const exitSetup = () => {
    navigate(firstRunExitPath(workspaceId, projectId), { replace: true })
  }

  const createProjectAndContinue = async (data: CreateProjectFormData) => {
    const name = data.name.trim()
    if (!name) return

    try {
      const created = await createProject.mutateAsync({
        workspace_id: workspaceId,
        name,
        slug: slugify(name, 'project'),
      })

      selectProject({
        id: created.id,
        workspace_id: created.workspace_id,
        name: created.name,
        slug: created.slug,
      })
      form.reset()
      toast.success('Project created')
      navigate(firstRunProjectSetupPath(workspaceId, created.id), { replace: true })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create Project')
    }
  }

  const openPlayground = (agent: Agent) => {
    if (!projectId) return
    navigate(firstRunPlaygroundPath(workspaceId, projectId, agent.id), { replace: true })
  }

  return (
    <FirstRunShell
      workspaceName={workspace.name}
      projectName={project?.name}
      activeStage={projectId ? 'agent' : 'project'}
      onExit={exitSetup}
    >
      {projectId ? (
        <FirstRunAgentSetup projectId={projectId} onCreated={openPlayground} />
      ) : (
        <FirstRunProjectStep
          form={form}
          pending={createProject.isPending}
          onSubmit={createProjectAndContinue}
        />
      )}
    </FirstRunShell>
  )
}
