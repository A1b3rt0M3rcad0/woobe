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
import { useOrganization } from '@/features/organizations/hooks'
import { useCreateProject, useProject } from '@/features/projects/hooks'
import { createProjectSchema, type CreateProjectFormData } from '@/features/projects/schemas'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { slugify } from '@/lib/slug'

export function firstRunProjectSetupPath(organizationId: string, projectId: string) {
  return `/organizations/${organizationId}/projects/${projectId}/setup`
}

export function firstRunPlaygroundPath(organizationId: string, projectId: string, agentId: string) {
  return `/organizations/${organizationId}/projects/${projectId}/agents/${agentId}/playground?firstRun=1`
}

export function firstRunExitPath(organizationId: string, projectId?: string) {
  return projectId
    ? `/organizations/${organizationId}/projects/${projectId}/agents`
    : `/organizations/${organizationId}/projects`
}

export default function FirstRunSetupPage() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId?: string }>()
  const navigate = useNavigate()
  const {
    currentOrganization,
    currentProject,
    selectOrganization,
    selectProject,
  } = useWorkspace()
  const organizationQuery = useOrganization(organizationId)
  const projectQuery = useProject(projectId)
  const createProject = useCreateProject(organizationId)
  const form = useForm<CreateProjectFormData>({
    resolver: zodResolver(createProjectSchema),
    defaultValues: { name: '' },
  })

  const organization = organizationQuery.data
  const project = projectQuery.data || (currentProject?.id === projectId ? currentProject : null)

  useEffect(() => {
    if (!organization || currentOrganization?.id === organization.id) return
    selectOrganization({
      id: organization.id,
      name: organization.name,
      slug: organization.slug,
    })
  }, [currentOrganization, organization, selectOrganization])

  useEffect(() => {
    if (!projectQuery.data || currentProject?.id === projectQuery.data.id) return
    selectProject({
      id: projectQuery.data.id,
      organization_id: projectQuery.data.organization_id,
      name: projectQuery.data.name,
      slug: projectQuery.data.slug,
    })
  }, [currentProject, projectQuery.data, selectProject])

  if (!organizationId) return <ErrorState message="Organization not found" />
  if (organizationQuery.isLoading) return <LoadingState message="Opening first-run setup" />
  if (organizationQuery.isError) return <ErrorState error={organizationQuery.error} onRetry={organizationQuery.refetch} />
  if (!organization) return <ErrorState message="Organization not found" />
  if (projectId && projectQuery.isLoading && !project) return <LoadingState message="Opening Project setup" />
  if (projectId && projectQuery.isError) return <ErrorState error={projectQuery.error} onRetry={projectQuery.refetch} />

  const exitSetup = () => {
    navigate(firstRunExitPath(organizationId, projectId), { replace: true })
  }

  const createProjectAndContinue = async (data: CreateProjectFormData) => {
    const name = data.name.trim()
    if (!name) return

    try {
      const created = await createProject.mutateAsync({
        organization_id: organizationId,
        name,
        slug: slugify(name, 'project'),
      })

      selectProject({
        id: created.id,
        organization_id: created.organization_id,
        name: created.name,
        slug: created.slug,
      })
      form.reset()
      toast.success('Project created')
      navigate(firstRunProjectSetupPath(organizationId, created.id), { replace: true })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create Project')
    }
  }

  const openPlayground = (agent: Agent) => {
    if (!projectId) return
    navigate(firstRunPlaygroundPath(organizationId, projectId, agent.id), { replace: true })
  }

  return (
    <FirstRunShell
      organizationName={organization.name}
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
