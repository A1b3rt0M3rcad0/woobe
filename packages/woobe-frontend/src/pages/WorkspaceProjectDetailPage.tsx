import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpen,
  Bot,
  Key,
  Play,
  Save,
  Wrench,
} from 'lucide-react'
import { Button, Card, Field, FieldError, FieldLabel, Input } from '@woobe/ui'
import { toast } from 'sonner'
import { useProject, useUpdateProject } from '@/features/projects/hooks'
import { createProjectSchema, type CreateProjectFormData } from '@/features/projects/schemas'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'

const quickLinks = [
  { label: 'Agents', icon: Bot, tone: 'text-blue-300', segment: 'agents' },
  { label: 'Knowledge', icon: BookOpen, tone: 'text-emerald-300', segment: 'knowledge' },
  { label: 'Tools', icon: Wrench, tone: 'text-amber-300', segment: 'tools' },
  { label: 'API Keys', icon: Key, tone: 'text-violet-300', segment: 'api-keys' },
  { label: 'Usage', icon: BarChart3, tone: 'text-slate-300', segment: 'usage' },
  { label: 'Traces', icon: Activity, tone: 'text-cyan-300', segment: 'traces' },
]

function SettingsSectionHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="border-b border-border px-4 py-3.5">
      <h2 className="font-mono text-[11px] font-bold tracking-[0.02em] text-slate-50">{title}</h2>
      {description && <p className="mt-1 font-mono text-[9px] leading-4 text-muted-foreground">{description}</p>}
    </div>
  )
}

export default function WorkspaceProjectDetailPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>()
  const navigate = useNavigate()
  const { selectProject } = useWorkspace()
  const [savedAt, setSavedAt] = useState<string | null>(null)

  const { data: project, isLoading, isError, error, refetch } = useProject(projectId)
  const updateProject = useUpdateProject()

  const form = useForm<CreateProjectFormData>({
    resolver: zodResolver(createProjectSchema),
    values: project ? { name: project.name, slug: project.slug } : undefined,
  })

  const handleSave = async (data: CreateProjectFormData) => {
    if (!projectId) return
    try {
      const updated = await updateProject.mutateAsync({
        id: projectId,
        data: { name: data.name, slug: data.slug || undefined },
      })
      selectProject({
        id: updated.id,
        workspace_id: updated.workspace_id,
        name: updated.name,
        slug: updated.slug,
      })
      setSavedAt(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
      toast.success('Project updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update project')
    }
  }

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />
  if (!project) return <ErrorState message="Project not found" />

  const projectBase = `/workspaces/${workspaceId}/projects/${projectId}`
  const metadata = [
    { label: 'Project ID', value: project.id },
    { label: 'Workspace ID', value: project.workspace_id },
    { label: 'Status', value: project.status || 'active' },
    ...(project.created_at ? [{ label: 'Created', value: new Date(project.created_at).toLocaleDateString() }] : []),
    ...(project.updated_at ? [{ label: 'Updated', value: new Date(project.updated_at).toLocaleDateString() }] : []),
  ]

  return (
    <div className="relative min-h-full overflow-hidden bg-background">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 [background-image:linear-gradient(rgba(148,163,184,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.025)_1px,transparent_1px)] [background-size:32px_32px]"
      />

      <div className="relative mx-auto w-full max-w-[1280px] space-y-4 px-4 py-4 sm:px-5 sm:py-5">
        <header className="border border-border bg-surface/[0.96] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.018)]">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
                <span className="h-1.5 w-1.5 bg-primary" />
                Project configuration
              </div>
              <h1 className="mt-2 truncate font-mono text-base font-bold tracking-[0.01em] text-slate-50">Project Settings</h1>
              <p className="mt-1 truncate font-mono text-[9px] text-muted-foreground">
                {project.name} · /{project.slug} · {project.status || 'active'}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" onClick={() => navigate(`/workspaces/${workspaceId}/projects`)}>
                <ArrowLeft className="h-3.5 w-3.5" />
                Projects
              </Button>
              <Button onClick={() => navigate(projectBase)}>
                Open overview
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </header>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="overflow-hidden border-border bg-surface/[0.96] p-0 shadow-none">
            <SettingsSectionHeader
              title="Project Details"
              description="Mutable project identity and technical metadata."
            />

            <form onSubmit={form.handleSubmit(handleSave)} noValidate>
              <div className="grid gap-4 p-4 md:grid-cols-2">
                <Field>
                  <FieldLabel htmlFor="project-settings-name">Name</FieldLabel>
                  <Input
                    id="project-settings-name"
                    placeholder="Project name"
                    invalid={Boolean(form.formState.errors.name)}
                    aria-describedby={form.formState.errors.name ? 'project-settings-name-error' : undefined}
                    {...form.register('name')}
                  />
                  {form.formState.errors.name?.message && (
                    <FieldError id="project-settings-name-error">{form.formState.errors.name.message}</FieldError>
                  )}
                </Field>

                <Field>
                  <FieldLabel htmlFor="project-settings-slug">Slug</FieldLabel>
                  <Input
                    id="project-settings-slug"
                    placeholder="project-slug"
                    invalid={Boolean(form.formState.errors.slug)}
                    aria-describedby={form.formState.errors.slug ? 'project-settings-slug-error' : undefined}
                    {...form.register('slug')}
                  />
                  {form.formState.errors.slug?.message && (
                    <FieldError id="project-settings-slug-error">{form.formState.errors.slug.message}</FieldError>
                  )}
                </Field>
              </div>

              <div className="border-t border-border">
                <div className="grid sm:grid-cols-2">
                  {metadata.map((item, index) => (
                    <div
                      key={item.label}
                      className={`min-w-0 border-b border-border/70 px-4 py-3 ${index % 2 === 0 ? 'sm:border-r' : ''}`}
                    >
                      <p className="font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">{item.label}</p>
                      <p className="mt-1 truncate font-mono text-[10px] font-medium text-slate-200" title={item.value}>
                        {item.value}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex flex-col gap-3 border-t border-border bg-control/45 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="font-mono text-[8px] text-muted-foreground">
                  {savedAt ? `Last saved at ${savedAt}` : form.formState.isDirty ? 'Unsaved project changes' : 'Project configuration is up to date'}
                </p>
                <Button type="submit" loading={updateProject.isPending} disabled={!form.formState.isDirty && !updateProject.isPending}>
                  <Save className="h-3.5 w-3.5" />
                  Save changes
                </Button>
              </div>
            </form>
          </Card>

          <div className="space-y-4">
            <Card className="overflow-hidden border-border bg-surface/[0.96] p-0 shadow-none">
              <SettingsSectionHeader title="Project Navigation" description="Open project-scoped operational surfaces." />
              <nav className="divide-y divide-border/70">
                {quickLinks.map((link) => {
                  const Icon = link.icon
                  return (
                    <button
                      key={link.label}
                      type="button"
                      onClick={() => navigate(`${projectBase}/${link.segment}`)}
                      className="group flex min-h-10 w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition-colors hover:bg-accent/45 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-primary"
                    >
                      <span className="flex min-w-0 items-center gap-2.5">
                        <Icon className={`h-3.5 w-3.5 shrink-0 ${link.tone}`} />
                        <span className="truncate font-mono text-[10px] font-medium text-slate-200">{link.label}</span>
                      </span>
                      <ArrowRight className="h-3 w-3 shrink-0 text-muted transition-colors group-hover:text-primary-light" />
                    </button>
                  )
                })}
              </nav>
            </Card>

            <Card className="overflow-hidden border-border bg-surface/[0.96] p-0 shadow-none">
              <SettingsSectionHeader title="Agent Playground" description="Create or select an Agent before starting an interactive run." />
              <div className="p-4">
                <Button variant="outline" className="w-full justify-between" onClick={() => navigate(`${projectBase}/agents`)}>
                  <span className="flex items-center gap-2">
                    <Play className="h-3.5 w-3.5 text-primary-light" />
                    Open Agents
                  </span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
