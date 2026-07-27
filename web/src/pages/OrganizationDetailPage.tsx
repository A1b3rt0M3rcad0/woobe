import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useOrganization, useUpdateOrganization, useOrganizationMembers, useOrganizationInvites, useCreateInvite } from '@/features/organizations/hooks'
import {
  useGrantProjectAccess,
  useProjectMembers,
  useProjectsForAccessManagement,
  useRevokeProjectAccess,
} from '@/features/projects/hooks'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Dialog } from '@/components/ui/Dialog'
import { Table } from '@/components/ui/Table'
import { StatusBadge } from '@/components/common/StatusBadge'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { updateOrganizationSchema, inviteMemberSchema, type UpdateOrganizationFormData, type InviteMemberFormData } from '@/features/organizations/schemas'
import { Save, X, ArrowRight, UserPlus, Users } from 'lucide-react'
import { toast } from 'sonner'
import type { Member, Invite } from '@/features/organizations/types'
import type { ProjectAccessMember } from '@/features/projects/types'

export default function OrganizationDetailPage() {
  const { organizationId } = useParams<{ organizationId: string }>()
  const navigate = useNavigate()
  const { selectOrganization } = useWorkspace()

  const { data: org, isLoading, isError, error, refetch } = useOrganization(organizationId)
  const updateOrg = useUpdateOrganization()
  const { data: members } = useOrganizationMembers(organizationId)
  const { data: invites } = useOrganizationInvites(organizationId)
  const createInvite = useCreateInvite()
  const { data: projectAccess } = useProjectsForAccessManagement(organizationId)
  const grantProjectAccess = useGrantProjectAccess()
  const revokeProjectAccess = useRevokeProjectAccess()

  const [showInvite, setShowInvite] = useState(false)
  const [selectedProjectId, setSelectedProjectId] = useState<string | undefined>()
  const [accessEmail, setAccessEmail] = useState('')
  const { data: selectedProjectMembers, isLoading: isLoadingProjectMembers } = useProjectMembers(selectedProjectId)

  const form = useForm<UpdateOrganizationFormData>({
    resolver: zodResolver(updateOrganizationSchema),
    values: org ? { name: org.name, slug: org.slug } : undefined,
  })

  const inviteForm = useForm<InviteMemberFormData>({
    resolver: zodResolver(inviteMemberSchema),
    defaultValues: { role: 'member' },
  })

  const handleSave = async (data: UpdateOrganizationFormData) => {
    if (!organizationId) return
    try {
      const updated = await updateOrg.mutateAsync({
        id: organizationId,
        data: { name: data.name, slug: data.slug || undefined },
      })
      selectOrganization({ id: updated.id, name: updated.name, slug: updated.slug })
      toast.success('Organization updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update organization')
    }
  }

  const handleInvite = async (data: InviteMemberFormData) => {
    if (!organizationId) return
    try {
      await createInvite.mutateAsync({
        orgId: organizationId,
        data: { email: data.email, role: data.role },
      })
      toast.success('Invite sent')
      setShowInvite(false)
      inviteForm.reset()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to send invite')
    }
  }

  const handleGrantProjectAccess = async () => {
    if (!selectedProjectId || !accessEmail.trim()) return
    try {
      await grantProjectAccess.mutateAsync({
        projectId: selectedProjectId,
        email: accessEmail.trim(),
      })
      setAccessEmail('')
      toast.success('Project access granted')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to grant project access')
    }
  }

  const handleRevokeProjectAccess = async (member: ProjectAccessMember) => {
    if (!selectedProjectId || member.implicit_owner) return
    try {
      await revokeProjectAccess.mutateAsync({
        projectId: selectedProjectId,
        userId: member.user_id,
      })
      toast.success('Project access removed')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove project access')
    }
  }

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />
  if (!org) return <ErrorState message="Organization not found" />

  const selectedProject = projectAccess?.find((project) => project.id === selectedProjectId)

  const memberColumns = [
    { key: 'user_id', header: 'User ID' },
    { key: 'role', header: 'Role', render: (m: Member) => <StatusBadge status={m.role} /> },
    { key: 'status', header: 'Status', render: (m: Member) => <StatusBadge status={m.status} /> },
  ]

  const inviteColumns = [
    { key: 'email', header: 'Email' },
    { key: 'role', header: 'Role', render: (i: Invite) => <StatusBadge status={i.role} /> },
    { key: 'status', header: 'Status', render: (i: Invite) => <StatusBadge status={i.status} /> },
    { key: 'expires_at', header: 'Expires' },
  ]

  const projectMemberColumns = [
    { key: 'email', header: 'Member' },
    {
      key: 'access',
      header: 'Access',
      render: (m: ProjectAccessMember) => (
        <StatusBadge status={m.implicit_owner ? 'owner · full access' : 'full access'} />
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (m: ProjectAccessMember) => m.implicit_owner ? null : (
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={!selectedProjectMembers?.can_manage || revokeProjectAccess.isPending}
          onClick={() => handleRevokeProjectAccess(m)}
        >
          Remove
        </Button>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title={org.name}
        description={`/${org.slug} · ${org.status}`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => navigate(`/organizations`)}>
              <X className="mr-2 h-4 w-4" />
              Back to organizations
            </Button>
            <Button onClick={() => navigate(`/organizations/${organizationId}/projects`)}>
              Go to projects
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Details</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={form.handleSubmit(handleSave)} className="space-y-4">
              <Input {...form.register('name')} error={form.formState.errors.name?.message} placeholder="Organization name" />
              <Input {...form.register('slug')} error={form.formState.errors.slug?.message} placeholder="slug" />
              <div className="flex items-center gap-2 text-sm text-muted">
                <span>ID: {org.id}</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-muted">
                <span>Status: {org.status}</span>
              </div>
              {org.created_at && (
                <div className="flex items-center gap-2 text-sm text-muted">
                  <span>Created: {new Date(org.created_at).toLocaleDateString()}</span>
                </div>
              )}
              <div className="flex justify-end">
                <Button type="submit" loading={updateOrg.isPending}>
                  <Save className="mr-2 h-4 w-4" />
                  Save Changes
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Members</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              {members && members.length > 0 ? (
                <div className="p-0">
                  <Table columns={memberColumns} data={members} keyExtractor={(m) => m.id} />
                </div>
              ) : (
                <p className="text-sm text-muted">No members found.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Invites</CardTitle>
                <Button size="sm" onClick={() => setShowInvite(true)}>
                  <UserPlus className="mr-1 h-4 w-4" />
                  Invite
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {invites && invites.length > 0 ? (
                <div className="p-0">
                  <Table columns={inviteColumns} data={invites} keyExtractor={(i) => i.id} />
                </div>
              ) : (
                <p className="text-sm text-muted">No pending invites.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {projectAccess && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Users className="h-4 w-4" />
              Project access
            </CardTitle>
            <p className="text-sm text-muted">
              Project access is binary: a member listed here can operate the entire Project. Organization membership alone does not grant Project access.
            </p>
          </CardHeader>
          <CardContent>
            {projectAccess.length === 0 ? (
              <p className="text-sm text-muted">No Projects found in this Organization.</p>
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {projectAccess.map((project) => (
                  <button
                    type="button"
                    key={project.id}
                    className="rounded-lg border border-border p-4 text-left transition-colors hover:border-primary/50"
                    onClick={() => setSelectedProjectId(project.id)}
                  >
                    <p className="font-medium">{project.name}</p>
                    <p className="mt-1 text-xs text-muted">/{project.slug}</p>
                    <p className="mt-3 text-xs text-muted">
                      {project.member_count} explicit {project.member_count === 1 ? 'member' : 'members'} · owner has implicit access
                    </p>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Dialog open={showInvite} onClose={() => setShowInvite(false)} title="Invite Member">
        <form onSubmit={inviteForm.handleSubmit(handleInvite)} className="space-y-4">
          <Input {...inviteForm.register('email')} error={inviteForm.formState.errors.email?.message} placeholder="Email address" />
          <div>
            <label className="block text-sm font-medium text-muted mb-1">Organization role</label>
            <select
              {...inviteForm.register('role')}
              className="flex h-9 w-full rounded-lg border border-border bg-transparent px-3 py-1 text-sm"
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <p className="text-xs text-muted">Joining the Organization does not automatically grant access to its Projects.</p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setShowInvite(false)}>Cancel</Button>
            <Button type="submit" loading={createInvite.isPending}>Send Invite</Button>
          </div>
        </form>
      </Dialog>

      <Dialog
        open={Boolean(selectedProjectId)}
        onClose={() => {
          setSelectedProjectId(undefined)
          setAccessEmail('')
        }}
        title={selectedProject ? `Project access · ${selectedProject.name}` : 'Project access'}
      >
        <div className="space-y-4">
          <div>
            <p className="text-sm font-medium">Grant full Project access</p>
            <p className="mt-1 text-xs text-muted">The user must already be an active member of this Organization.</p>
          </div>
          <div className="flex gap-2">
            <Input
              value={accessEmail}
              onChange={(event) => setAccessEmail(event.target.value)}
              placeholder="member@company.com"
            />
            <Button
              type="button"
              onClick={handleGrantProjectAccess}
              loading={grantProjectAccess.isPending}
              disabled={!accessEmail.trim() || !selectedProjectMembers?.can_manage}
            >
              Add access
            </Button>
          </div>

          {isLoadingProjectMembers ? (
            <LoadingState message="Loading Project members" variant="panel" />
          ) : selectedProjectMembers?.members.length ? (
            <Table
              columns={projectMemberColumns}
              data={selectedProjectMembers.members}
              keyExtractor={(member) => member.id ?? `owner-${member.user_id}`}
            />
          ) : (
            <p className="text-sm text-muted">No explicit Project members.</p>
          )}
        </div>
      </Dialog>
    </div>
  )
}
