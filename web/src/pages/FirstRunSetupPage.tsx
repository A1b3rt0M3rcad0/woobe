import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Check,
  Circle,
  FolderKanban,
  Rocket,
} from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Button } from '@/components/ui/Button'
import { DialogPresentationProvider } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { CreateAgentFlowModal } from '@/features/agents/components/CreateAgentFlowModal'
import type { Agent } from '@/features/agents/types'
import { useOrganization } from '@/features/organizations/hooks'
import { useCreateProject } from '@/features/projects/hooks'
import { createProjectSchema, type CreateProjectFormData } from '@/features/projects/schemas'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { slugify } from '@/lib/slug'

type SetupStage = 'project' | 'agent'

const SETUP_STEPS = [
  { key: 'project', label: 'Project' },
  { key: 'agent', label: 'Agent' },
  { key: 'test', label: 'First test' },
] as const

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

function SetupProgress({ stage }: { stage: SetupStage }) {
  const currentIndex = stage === 'project' ? 0 : 1

  return (
    <div className="space-y-4">
      {SETUP_STEPS.map((item, index) => {
        const completed = index < currentIndex
        const active = index === currentIndex

        return (
          <div key={item.key} className="flex items-center gap-3">
            <span
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${
                completed
                  ? 'border-primary/50 bg-primary/15 text-primary-light'
                  : active
                    ? 'border-primary bg-primary/10 text-white'
                    : 'border-border bg-background text-muted'
              }`}
            >
              {completed ? <Check className="h-4 w-4" /> : index + 1}
            </span>
            <div>
              <p className={`text-sm ${active ? 'font-medium text-white' : completed ? 'text-white/85' : 'text-muted'}`}>
                {item.label}
              </p>
              {active && (
                <p className="mt-0.5 text-xs text-muted">
                  {stage === 'project' ? 'Create the technical workspace.' : 'Configure the first operational Agent.'}
                </p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
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
  const createProject = useCreateProject(organizationId)
  const form = useForm<CreateProjectFormData>({
    resolver: zodResolver(createProjectSchema),
    defaultValues: { name: '' },
  })

  const stage: SetupStage = projectId ? 'agent' : 'project'
  const organization = organizationQuery.data
  const selectedProject = currentProject?.id === projectId ? currentProject : null

  useEffect(() => {
    if (!organization || currentOrganization?.id === organization.id) return
    selectOrganization({
      id: organization.id,
      name: organization.name,
      slug: organization.slug,
    })
  }, [currentOrganization, organization, selectOrganization])

  if (!organizationId) return <ErrorState message="Organization not found" />
  if (organizationQuery.isLoading) return <LoadingState message="Opening first-run setup" />
  if (organizationQuery.isError) return <ErrorState error={organizationQuery.error} onRetry={organizationQuery.refetch} />
  if (!organization) return <ErrorState message="Organization not found" />

  const exitSetup = () => {
    navigate(firstRunExitPath(organizationId, projectId), { replace: true })
  }

  const createProjectAndContinue = async (data: CreateProjectFormData) => {
    const name = data.name.trim()
    if (!name) return

    try {
      const project = await createProject.mutateAsync({
        organization_id: organizationId,
        name,
        slug: slugify(name, 'project'),
      })

      selectProject({
        id: project.id,
        organization_id: project.organization_id,
        name: project.name,
        slug: project.slug,
      })
      form.reset()
      toast.success('Project created')
      navigate(firstRunProjectSetupPath(organizationId, project.id), { replace: true })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create Project')
    }
  }

  const openPlayground = (agent: Agent) => {
    if (!projectId) return
    navigate(firstRunPlaygroundPath(organizationId, projectId, agent.id), { replace: true })
  }

  return (
    <div className="min-h-full bg-background">
      <header className="border-b border-border/80 bg-surface/45">
        <div className="mx-auto flex w-full max-w-7xl items-start justify-between gap-6 px-5 py-6 sm:px-8 lg:px-10">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary/[0.06] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.16em] text-primary-light">
              <Rocket className="h-3.5 w-3.5" />
              First run setup
            </div>
            <h1 className="mt-4 text-2xl font-semibold tracking-tight text-white">Launch your first Agent</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              Create the Project boundary, configure the Agent and continue directly to its first Playground test.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={exitSetup}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Exit setup
          </Button>
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-7xl gap-6 px-5 py-6 sm:px-8 lg:grid-cols-[260px_minmax(0,1fr)] lg:px-10 lg:py-8">
        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <section className="rounded-xl border border-border/90 bg-surface/65 p-5">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Launch progress</p>
            <div className="mt-5">
              <SetupProgress stage={stage} />
            </div>
          </section>

          <section className="rounded-xl border border-border/90 bg-background/55 p-5">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Context</p>
            <div className="mt-4 space-y-4">
              <div>
                <p className="text-xs text-muted">Organization</p>
                <p className="mt-1 truncate text-sm font-medium text-white">{organization.name}</p>
              </div>
              <div className="h-px bg-border/80" />
              <div>
                <p className="text-xs text-muted">Project</p>
                <p className="mt-1 truncate text-sm font-medium text-white">
                  {selectedProject?.name || (stage === 'project' ? 'Not created yet' : 'Opening Project')}
                </p>
              </div>
            </div>
          </section>
        </aside>

        <main className="min-w-0">
          {stage === 'project' ? (
            <section className="overflow-hidden rounded-2xl border border-border/90 bg-surface/60 shadow-xl shadow-black/10">
              <div className="border-b border-border/80 px-6 py-5 sm:px-8">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
                  <FolderKanban className="h-5 w-5" />
                </div>
                <h2 className="mt-5 text-lg font-semibold text-white">Create the Project for your Agent</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                  The Project isolates Agents, Knowledge, Tools, credentials, runtime and observability. You can rename and configure it later.
                </p>
              </div>

              <form onSubmit={form.handleSubmit(createProjectAndContinue)} className="space-y-6 px-6 py-6 sm:px-8 sm:py-8">
                <div className="max-w-2xl">
                  <label className="mb-2 block text-sm font-medium text-white">Project name</label>
                  <Input
                    {...form.register('name')}
                    error={form.formState.errors.name?.message}
                    placeholder="Customer support platform"
                    autoFocus
                  />
                  <p className="mt-2 text-xs leading-5 text-muted">
                    Use the product, team or technical boundary this Project will represent.
                  </p>
                </div>

                <div className="grid gap-3 rounded-xl border border-border/80 bg-background/50 p-4 sm:grid-cols-3">
                  <div className="flex items-start gap-3">
                    <Circle className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
                    <div>
                      <p className="text-sm font-medium text-white">Project</p>
                      <p className="mt-1 text-xs leading-5 text-muted">Create the isolation boundary.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Bot className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
                    <div>
                      <p className="text-sm font-medium text-white">Agent</p>
                      <p className="mt-1 text-xs leading-5 text-muted">Define instructions and model.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Rocket className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
                    <div>
                      <p className="text-sm font-medium text-white">Playground</p>
                      <p className="mt-1 text-xs leading-5 text-muted">Run the first operational test.</p>
                    </div>
                  </div>
                </div>

                <div className="flex justify-end border-t border-border/80 pt-5">
                  <Button type="submit" loading={createProject.isPending}>
                    Create Project and continue
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </div>
              </form>
            </section>
          ) : projectId ? (
            <div className="space-y-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary-light">Project created</p>
                <h2 className="mt-2 text-xl font-semibold text-white">Configure the first Agent</h2>
                <p className="mt-2 text-sm leading-6 text-muted">
                  Define its behavior and connect the model required to enter the Playground.
                </p>
              </div>

              <DialogPresentationProvider presentation="embedded">
                <CreateAgentFlowModal
                  open
                  projectId={projectId}
                  onClose={exitSetup}
                  onCreated={openPlayground}
                />
              </DialogPresentationProvider>
            </div>
          ) : null}
        </main>
      </div>
    </div>
  )
}
