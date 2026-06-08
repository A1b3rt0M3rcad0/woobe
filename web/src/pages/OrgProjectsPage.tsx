import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { useProjects, useCreateProject } from '@/features/projects/hooks'
import { useOrganization } from '@/features/organizations/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { createProjectSchema, type CreateProjectFormData } from '@/features/projects/schemas'
import { FolderKanban, Plus, ArrowRight, Eye } from 'lucide-react'
import { toast } from 'sonner'

export default function OrgProjectsPage() {
  const { organizationId } = useParams<{ organizationId: string }>()
  const navigate = useNavigate()
  const { selectProject, currentOrganization } = useWorkspace()

  const { data: org, isLoading: orgLoading } = useOrganization(organizationId)
  const { data: projects, isLoading: projectsLoading, isError, error, refetch } = useProjects(organizationId)
  const createProject = useCreateProject(organizationId)

  const [showCreate, setShowCreate] = useState(false)

  const form = useForm<CreateProjectFormData>({
    resolver: zodResolver(createProjectSchema),
  })

  const handleCreate = async (data: CreateProjectFormData) => {
    if (!organizationId) return
    try {
      const project = await createProject.mutateAsync({
        organization_id: organizationId,
        name: data.name,
        slug: data.slug || data.name.toLowerCase().replace(/\s+/g, '-'),
      })
      toast.success('Project created')
      setShowCreate(false)
      form.reset()
      selectProject({
        id: project.id,
        organization_id: project.organization_id,
        name: project.name,
        slug: project.slug,
      })
      navigate(`/organizations/${organizationId}/projects/${project.id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create project')
    }
  }

  const handleSelect = (p: { id: string; organization_id: string; name: string; slug: string }) => {
    selectProject(p)
    navigate(`/organizations/${organizationId}/projects/${p.id}`)
  }

  if (orgLoading || projectsLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />
  if (!org) return <ErrorState message="Organization not found" />

  return (
    <div>
      <PageHeader
        title={`Projects / ${org.name}`}
        description={org.slug}
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New Project
          </Button>
        }
      />

      <div className="mb-4">
        <Button variant="outline" size="sm" onClick={() => navigate(`/organizations/${organizationId}/settings`)}>
          <Eye className="mr-1 h-4 w-4" />
          Organization Settings
        </Button>
      </div>

      {!projects || projects.length === 0 ? (
        <EmptyState
          icon={<FolderKanban className="h-12 w-12" />}
          title="No projects yet"
          description="Create a project to start building AI agents."
          action={
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Project
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <Card key={p.id} className="hover:border-primary/50 transition-colors">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  {p.name}
                </CardTitle>
                <CardDescription>
                  /{p.slug} {p.status && `· ${p.status}`}
                </CardDescription>
                <div className="flex gap-2 mt-3">
                  <Button size="sm" variant="outline" onClick={() => handleSelect(p)}>
                    Open
                    <ArrowRight className="ml-1 h-3 w-3" />
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => navigate(`/organizations/${organizationId}/projects/${p.id}/settings`)}>
                    <Eye className="mr-1 h-3 w-3" />
                    Settings
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="Create Project">
        <form onSubmit={form.handleSubmit(handleCreate)} className="space-y-4">
          <Input {...form.register('name')} error={form.formState.errors.name?.message} placeholder="Project name" />
          <Input {...form.register('slug')} error={form.formState.errors.slug?.message} placeholder="slug (optional)" />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button type="submit" loading={createProject.isPending}>Create</Button>
          </div>
        </form>
      </Dialog>
    </div>
  )
}
