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
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Button,
  Dialog,
  Field,
  FieldError,
  FieldLabel,
  Input,
  SectionBlock,
  Skeleton,
  TechnicalListItem,
} from '@woobe/ui'
import { toast } from 'sonner'

import { ProjectEnvironmentSettings } from '@/features/projects/components/ProjectEnvironmentSettings'
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
  { label: 'Agents', icon: Bot, segment: 'agents' },
  { label: 'Knowledge', icon: BookOpen, segment: 'knowledge' },
  { label: 'Tools', icon: Wrench, segment: 'tools' },
  { label: 'API Keys', icon: Key, segment: 'api-keys' },
  { label: 'Usage', icon: BarChart3, segment: 'usage' },
  { label: 'Traces', icon: Activity, segment: 'traces' },
]

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
      className="max-w-dialog-wide"
      scrollMode="content"
      contentClassName="p-0"
    >
      {projectQuery.isPending ? (
        <div className="grid gap-ui-md p-ui-lg" aria-label="Loading project settings">
          <Skeleton className="h-control-row w-full" />
          <Skeleton className="h-44 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : projectQuery.isError || !project ? (
        <div className="p-ui-lg">
          <Alert variant="destructive">
            <AlertTitle>Project settings unavailable</AlertTitle>
            <AlertDescription>
              {projectQuery.error instanceof Error ? projectQuery.error.message : 'Project not found'}
            </AlertDescription>
            <Button variant="outline" size="sm" className="mt-ui-md" onClick={() => void projectQuery.refetch()}>Retry</Button>
          </Alert>
        </div>
      ) : (
        <div>
          <div className="border-b border-border bg-background/20 p-ui-md">
            <TechnicalListItem
              label={project.name}
              description={`/${project.slug}`}
              meta={`${project.status || 'active'} · ${project.id}`}
              trailing={(
                <Button size="sm" variant="outline" onClick={() => openProjectSurface()}>
                  Open overview
                  <ArrowRight className="h-icon w-icon" />
                </Button>
              )}
            />
          </div>

          <div className="lg:flex">
            <section className="min-w-0 flex-1 border-b border-border p-ui-md lg:border-b-0 lg:border-r">
              <form onSubmit={form.handleSubmit(handleSave)} noValidate className="grid gap-ui-md">
                <SectionBlock
                  title="Project details"
                  description="Mutable project identity used across project-scoped operational surfaces."
                >
                  <div className="grid gap-ui-md md:grid-cols-2">
                    <Field>
                      <FieldLabel htmlFor="project-settings-dialog-name">Name</FieldLabel>
                      <Input
                        id="project-settings-dialog-name"
                        placeholder="Project name"
                        invalid={Boolean(form.formState.errors.name)}
                        aria-describedby={form.formState.errors.name ? 'project-settings-dialog-name-error' : undefined}
                        {...form.register('name')}
                      />
                      {form.formState.errors.name?.message ? (
                        <FieldError id="project-settings-dialog-name-error">{form.formState.errors.name.message}</FieldError>
                      ) : null}
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
                      {form.formState.errors.slug?.message ? (
                        <FieldError id="project-settings-dialog-slug-error">{form.formState.errors.slug.message}</FieldError>
                      ) : null}
                    </Field>
                  </div>
                </SectionBlock>

                <ProjectEnvironmentSettings projectId={projectId} />

                <SectionBlock
                  title="Technical metadata"
                  description="Stable identifiers and lifecycle timestamps for this Project."
                  density="compact"
                >
                  <div className="grid gap-ui-xs sm:grid-cols-2">
                    {metadata.map((item) => (
                      <TechnicalListItem
                        key={item.label}
                        label={item.label}
                        description={item.value}
                        title={item.value}
                      />
                    ))}
                  </div>
                </SectionBlock>

                <div className="flex flex-col gap-ui-sm border-t border-border pt-ui-md sm:flex-row sm:items-center sm:justify-between">
                  <p className="font-mono text-system-meta text-muted-foreground">
                    {savedAt ? `Last saved at ${savedAt}` : form.formState.isDirty ? 'Unsaved project changes' : 'Project configuration is up to date'}
                  </p>
                  <Button type="submit" size="sm" loading={updateProject.isPending} disabled={!form.formState.isDirty && !updateProject.isPending}>
                    <Save className="h-icon w-icon" />
                    Save changes
                  </Button>
                </div>
              </form>
            </section>

            <aside className="shrink-0 p-ui-md lg:w-dialog-sidebar">
              <SectionBlock
                title="Project navigation"
                description="Project-scoped operational surfaces."
                density="compact"
              >
                <nav className="grid gap-ui-xs">
                  {quickLinks.map((link) => {
                    const Icon = link.icon
                    return (
                      <TechnicalListItem
                        key={link.label}
                        label={link.label}
                        leading={<Icon className="h-icon w-icon text-muted-foreground" />}
                        trailing={<ArrowRight className="h-icon-sm w-icon-sm text-muted-foreground" />}
                        onClick={() => openProjectSurface(link.segment)}
                      />
                    )
                  })}
                </nav>

                <div className="mt-ui-md border-t border-border pt-ui-md">
                  <Button variant="outline" size="sm" className="w-full justify-between" onClick={() => openProjectSurface('agents')}>
                    <span className="flex items-center gap-ui-sm">
                      <Play className="h-icon w-icon text-primary-light" />
                      Open Agents
                    </span>
                    <ArrowRight className="h-icon-sm w-icon-sm" />
                  </Button>
                </div>
              </SectionBlock>
            </aside>
          </div>
        </div>
      )}
    </Dialog>
  )
}
