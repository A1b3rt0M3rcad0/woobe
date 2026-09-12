import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpen,
  Bot,
  Key,
  Play,
  Save,
  Wrench,
} from 'lucide-react'
import { Button, Dialog, Field, FieldError, FieldLabel, Input } from '@woobe/ui'
import { toast } from 'sonner'

import { useProject, useUpdateProject } from '@/features/projects/hooks'
import { createProjectSchema, type CreateProjectFormData } from '@/features/projects/schemas'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { workspaceProjectPath } from '@/lib/constants/routes'

interface ProjectSettingsDialogProps {
  open: boolean
  onClose: () => void
  workspaceId: string
  projectId: string
}

const quickLinks = [
  { label: 'Agents', icon: Bot, tone: 'text-blue-300', segment: 'agents' },
  { label: 'Knowledge', icon: BookOpen, tone: 'text-emerald-300', segment: 'knowledge' },
  { label: 'Tools', icon: Wrench, tone: 'text-amber-300', segment: 'tools' },
  { label: 'API Keys', icon: Key, tone: 'text-violet-300', segment: 'api-keys' },
  { label: 'Usage', icon: BarChart3, tone: 'text-slate-300', segment: 'usage' },
  { label: 'Traces', icon: Activity, tone: 'text-cyan-300', segment: 'traces' },
]

function SectionHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="border-b border-border px-4 py-3.5">
      <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-slate-100">{title}</h3>
      {description && <p className="mt-1 font-mono text-[8px] leading-4 text-muted-foreground">{description}</p>}
    </div>
  )
}

export function ProjectSettingsDialog({ open, onClose, workspaceId, projectId }: ProjectSettingsDialogProps) {
  const navigate = useNavigate()
  const { selectProject } = useWorkspace()
  const [savedAt, setSavedAt] = useState<string | null>(null)
  const projectQuery = useProject(projectId)
  const updateProject = useUpdateProject()
  const project = projectQuery.data

  const form = useForm<CreateProjectFormData>({
    resolver: zodResolver(createProjectSchema),
    values: project ? { name: project.name, slug: project.slug } : undefined,
  })

  const handleSave = async (data: CreateProjectFormData) => {
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
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update project')
    }
  }

  const openProjectSurface = (segment?: string) => {
    onClose()
    navigate(segment ? workspaceProjectPath(workspaceId, projectId, segment) : workspaceProjectPath(workspaceId, projectId))
  }

  const metadata = project ? [
    { label: 'Project ID', value: project.id },
    { label: 'Workspace ID', value: project.workspace_id },
    { label: 'Status', value: project.status || 'active' },
    ...(project.created_at ? [{ label: 'Created', value: new Date(project.created_at).toLocaleDateString() }] : []),
    ...(project.updated_at ? [{ label: 'Updated', value: new Date(project.updated_at).toLocaleDateString() }] : []),
  ] : []

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Project Settings"
      className="max-w-[980px]"
      contentClassName="max-h-[calc(100svh-8rem)] overflow-y-auto p-0 dialog-scrollbars"
    >
      {projectQuery.isPending ? (
        <div className="space-y-3 p-5" aria-label="Loading project settings">
          <div className="h-10 animate-pulse rounded-control border border-border bg-control/45" />
          <div className="h-44 animate-pulse rounded-container border border-border bg-control/35" />
        </div>
      ) : projectQuery.isError || !project ? (
        <div className="p-5 text-center">
          <p className="font-mono text-[10px] font-bold text-red-200">Project settings unavailable</p>
          <p className="mt-1 font-mono text-[8px] text-muted-foreground">
            {projectQuery.error instanceof Error ? projectQuery.error.message : 'Project not found'}
          </p>
          <Button variant="outline" size="sm" className="mt-4" onClick={() => void projectQuery.refetch()}>Retry</Button>
        </div>
      ) : (
        <div>
          <div className="flex flex-col gap-3 border-b border-border bg-control/35 px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="truncate font-mono text-[10px] font-bold text-slate-100">{project.name}</p>
              <p className="mt-0.5 truncate font-mono text-[8px] text-muted-foreground">/{project.slug} · {project.status || 'active'}</p>
            </div>
            <Button size="sm" variant="outline" onClick={() => openProjectSurface()}>
              Open overview
              <ArrowRight className="h-3 w-3" />
            </Button>
          </div>

          <div className="grid lg:grid-cols-[minmax(0,1fr)_300px]">
            <section className="border-b border-border lg:border-b-0 lg:border-r">
              <SectionHeader title="Project details" description="Mutable project identity and technical metadata." />
              <form onSubmit={form.handleSubmit(handleSave)} noValidate>
                <div className="grid gap-4 p-4 md:grid-cols-2">
                  <Field>
                    <FieldLabel htmlFor="project-settings-dialog-name">Name</FieldLabel>
                    <Input
                      id="project-settings-dialog-name"
                      placeholder="Project name"
                      invalid={Boolean(form.formState.errors.name)}
                      aria-describedby={form.formState.errors.name ? 'project-settings-dialog-name-error' : undefined}
                      {...form.register('name')}
                    />
                    {form.formState.errors.name?.message && (
                      <FieldError id="project-settings-dialog-name-error">{form.formState.errors.name.message}</FieldError>
                    )}
                  </Field>

                  <Field>
                    <FieldLabel htmlFor="project-settings-dialog-slug">Slug</FieldLabel>
                    <Input
                      id="project-settings-dialog-slug"
                      placeholder="project-slug"
                      invalid={Boolean(form.formState.errors.slug)}
                      aria-describedby={form.formState.errors.slug ? 'project-settings-dialog-slug-error' : undefined}
                      {...form.register('slug')}
                    />
                    {form.formState.errors.slug?.message && (
                      <FieldError id="project-settings-dialog-slug-error">{form.formState.errors.slug.message}</FieldError>
                    )}
                  </Field>
                </div>

                <div className="grid border-t border-border sm:grid-cols-2">
                  {metadata.map((item, index) => (
                    <div
                      key={item.label}
                      className={`min-w-0 border-b border-border/70 px-4 py-3 ${index % 2 === 0 ? 'sm:border-r' : ''}`}
                    >
                      <p className="font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">{item.label}</p>
                      <p className="mt-1 truncate font-mono text-[10px] font-medium text-slate-200" title={item.value}>{item.value}</p>
                    </div>
                  ))}
                </div>

                <div className="flex flex-col gap-3 border-t border-border bg-control/35 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="font-mono text-[8px] text-muted-foreground">
                    {savedAt ? `Last saved at ${savedAt}` : form.formState.isDirty ? 'Unsaved project changes' : 'Project configuration is up to date'}
                  </p>
                  <Button type="submit" size="sm" loading={updateProject.isPending} disabled={!form.formState.isDirty && !updateProject.isPending}>
                    <Save className="h-3 w-3" />
                    Save changes
                  </Button>
                </div>
              </form>
            </section>

            <aside>
              <SectionHeader title="Project navigation" description="Project-scoped operational surfaces." />
              <nav className="divide-y divide-border/70">
                {quickLinks.map((link) => {
                  const Icon = link.icon
                  return (
                    <button
                      key={link.label}
                      type="button"
                      onClick={() => openProjectSurface(link.segment)}
                      className="group flex min-h-10 w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition-colors hover:bg-accent/45 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-primary"
                    >
                      <span className="flex min-w-0 items-center gap-2.5">
                        <Icon className={`h-3.5 w-3.5 shrink-0 ${link.tone}`} />
                        <span className="truncate font-mono text-[10px] font-medium text-slate-200">{link.label}</span>
                      </span>
                      <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground transition-colors group-hover:text-primary-light" />
                    </button>
                  )
                })}
              </nav>
              <div className="border-t border-border p-4">
                <Button variant="outline" size="sm" className="w-full justify-between" onClick={() => openProjectSurface('agents')}>
                  <span className="flex items-center gap-2">
                    <Play className="h-3.5 w-3.5 text-primary-light" />
                    Open Agents
                  </span>
                  <ArrowRight className="h-3 w-3" />
                </Button>
              </div>
            </aside>
          </div>
        </div>
      )}
    </Dialog>
  )
}
