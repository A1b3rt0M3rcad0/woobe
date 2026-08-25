import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useProject, useUpdateProject } from '@/features/projects/hooks'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { createProjectSchema, type CreateProjectFormData } from '@/features/projects/schemas'
import { Save, X, Bot, BookOpen, Wrench, Key, BarChart3, Activity, Play, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'

const quickLinks = [
  { label: 'Agents', icon: Bot, color: 'text-primary', segment: 'agents' },
  { label: 'Knowledge', icon: BookOpen, color: 'text-emerald-400', segment: 'knowledge' },
  { label: 'Tools', icon: Wrench, color: 'text-yellow-400', segment: 'tools' },
  { label: 'API Keys', icon: Key, color: 'text-purple-400', segment: 'api-keys' },
  { label: 'Usage', icon: BarChart3, color: 'text-orange-400', segment: 'usage' },
  { label: 'Traces', icon: Activity, color: 'text-cyan-400', segment: 'traces' },
]

export default function WorkspaceProjectDetailPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>()
  const navigate = useNavigate()
  const { selectProject } = useWorkspace()

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
      toast.success('Project updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update project')
    }
  }

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />
  if (!project) return <ErrorState message="Project not found" />

  return (
    <div>
      <PageHeader
        title={project.name}
        description={`/${project.slug} · ${project.status || 'active'}`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => navigate(`/workspaces/${workspaceId}/projects`)}>
              <X className="mr-2 h-4 w-4" />
              Back to projects
            </Button>
            <Button onClick={() => navigate(`/workspaces/${workspaceId}/projects/${projectId}`)}>
              Open overview
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Project Details</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={form.handleSubmit(handleSave)} className="space-y-4">
                <Input {...form.register('name')} error={form.formState.errors.name?.message} placeholder="Project name" />
                <Input {...form.register('slug')} error={form.formState.errors.slug?.message} placeholder="slug" />
                <div className="space-y-2 text-sm text-muted">
                  <div><span className="font-medium text-white">ID:</span> {project.id}</div>
                  <div><span className="font-medium text-white">Workspace:</span> {project.workspace_id}</div>
                  <div><span className="font-medium text-white">Status:</span> {project.status || 'active'}</div>
                  {project.created_at && <div><span className="font-medium text-white">Created:</span> {new Date(project.created_at).toLocaleDateString()}</div>}
                  {project.updated_at && <div><span className="font-medium text-white">Updated:</span> {new Date(project.updated_at).toLocaleDateString()}</div>}
                </div>
                <div className="flex justify-end">
                  <Button type="submit" loading={updateProject.isPending}>
                    <Save className="mr-2 h-4 w-4" />
                    Save Changes
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>

        <div>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Quick Links</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {quickLinks.map((link) => (
                <Button
                  key={link.label}
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => navigate(`/workspaces/${workspaceId}/projects/${projectId}/${link.segment}`)}
                >
                  <link.icon className={`mr-2 h-4 w-4 ${link.color}`} />
                  {link.label}
                </Button>
              ))}
            </CardContent>
          </Card>

          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-lg">Playground</CardTitle>
            </CardHeader>
            <CardContent>
              <Button
                className="w-full"
                onClick={() => navigate(`/workspaces/${workspaceId}/projects/${projectId}/agents`)}
              >
                <Play className="mr-2 h-4 w-4" />
                Open Agents
              </Button>
              <p className="text-xs text-muted mt-2 text-center">Create or select an agent to use the playground</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
