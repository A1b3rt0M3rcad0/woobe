import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { useCreateOrganization } from '@/features/organizations/hooks'
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
import { createOrganizationSchema, type CreateOrganizationFormData } from '@/features/organizations/schemas'
import { Building2, Plus, ArrowRight, Eye } from 'lucide-react'
import { toast } from 'sonner'

export default function OrganizationsPage() {
  const { organizations, currentOrganization, selectOrganization, isLoadingOrganizations, workspaceError } = useWorkspace()
  const createOrg = useCreateOrganization()
  const navigate = useNavigate()
  const [showCreate, setShowCreate] = useState(false)

  const form = useForm<CreateOrganizationFormData>({
    resolver: zodResolver(createOrganizationSchema),
  })

  const handleCreate = async (data: CreateOrganizationFormData) => {
    try {
      const org = await createOrg.mutateAsync({
        name: data.name,
        slug: data.slug || data.name.toLowerCase().replace(/\s+/g, '-'),
      })
      toast.success('Organization created')
      setShowCreate(false)
      form.reset()
      selectOrganization({ id: org.id, name: org.name, slug: org.slug })
      navigate(`/organizations/${org.id}/projects`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create organization')
    }
  }

  const handleSelect = (org: { id: string; name: string; slug: string }) => {
    selectOrganization(org)
    navigate(`/organizations/${org.id}/projects`)
  }

  if (isLoadingOrganizations) return <LoadingState />
  if (workspaceError) return <ErrorState error={workspaceError} />

  return (
    <div>
      <PageHeader
        title="Organizations"
        description="Select or manage your organizations"
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create Organization
          </Button>
        }
      />

      {!organizations || organizations.length === 0 ? (
        <EmptyState
          icon={<Building2 className="h-12 w-12" />}
          title="No organizations yet"
          description="Create an organization to get started."
          action={
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Organization
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {organizations.map((org) => (
            <Card key={org.id} className="hover:border-primary/50 transition-colors">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Building2 className="h-5 w-5 text-primary" />
                    {org.name}
                  </span>
                </CardTitle>
                <CardDescription>/{org.slug}</CardDescription>
                <div className="flex gap-2 mt-3">
                  <Button
                    size="sm"
                    variant={org.id === currentOrganization?.id ? 'default' : 'outline'}
                    onClick={() => handleSelect(org)}
                  >
                    {org.id === currentOrganization?.id ? 'Selected' : 'Select'}
                    <ArrowRight className="ml-1 h-3 w-3" />
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => navigate(`/organizations/${org.id}/settings`)}
                  >
                    <Eye className="mr-1 h-3 w-3" />
                    Edit
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="Create Organization">
        <form onSubmit={form.handleSubmit(handleCreate)} className="space-y-4">
          <Input {...form.register('name')} error={form.formState.errors.name?.message} placeholder="Organization name" />
          <Input {...form.register('slug')} error={form.formState.errors.slug?.message} placeholder="slug (optional)" />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button type="submit" loading={createOrg.isPending}>Create</Button>
          </div>
        </form>
      </Dialog>
    </div>
  )
}
