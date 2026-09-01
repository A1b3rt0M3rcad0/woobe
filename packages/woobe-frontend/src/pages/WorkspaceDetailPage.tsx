import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Building2, Check, CreditCard, FolderKanban, Mail, ShieldCheck, UserMinus, UserPlus, Users } from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { PageHeader } from '@/components/common/PageHeader'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Tabs } from '@/components/ui/Tabs'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import {
  useCancelWorkspaceInvite,
  useCreateInvite,
  useWorkspaceDetail,
  useWorkspaceInvites,
  useWorkspaceMembers,
  useRemoveWorkspaceMember,
  useUpdateWorkspace,
} from '@/features/workspaces/hooks'
import {
  useGrantProjectAccess,
  useProjectMembers,
  useProjectsForAccessManagement,
  useRevokeProjectAccess,
} from '@/features/projects/hooks'
import type { Invite, Member } from '@/features/workspaces/types'
import type { ProjectAccessSubject } from '@/features/projects/types'

function formatDate(value?: string | null) {
  if (!value) return 'Not recorded'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Invalid date'
  return new Intl.DateTimeFormat('en-US', { day: '2-digit', month: 'short', year: 'numeric' }).format(date)
}

function initials(email: string) {
  return email.split('@')[0].split(/[._-]/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'U'
}

function SummaryCard({ label, value, detail, icon }: { label: string; value: string | number; detail: string; icon: ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-surface/65 p-4">
      <div className="flex items-start justify-between gap-4">
        <div><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">{label}</p><p className="mt-2 text-xl font-semibold text-white">{value}</p><p className="mt-1 text-xs text-muted">{detail}</p></div>
        <div className="rounded-lg border border-primary/20 bg-primary/10 p-2 text-primary-light">{icon}</div>
      </div>
    </div>
  )
}

function RoleChoice({ active, title, description, onClick }: { active: boolean; title: string; description: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className={`w-full rounded-xl border p-4 text-left transition-colors ${active ? 'border-primary/50 bg-primary/10' : 'border-border bg-background/35 hover:border-primary/30'}`}>
      <span className="flex items-start gap-3">
        <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${active ? 'border-primary bg-primary text-white' : 'border-border text-transparent'}`}><Check className="h-3 w-3" /></span>
        <span><span className="block text-sm font-semibold text-white">{title}</span><span className="mt-1 block text-xs leading-5 text-muted">{description}</span></span>
      </span>
    </button>
  )
}

export default function WorkspaceDetailPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const navigate = useNavigate()
  const { currentWorkspace, selectWorkspace } = useWorkspace()
  const currentRole = currentWorkspace?.membership_role ?? 'member'
  const canManageWorkspace = currentRole === 'owner' || currentRole === 'admin'
  const canInviteAdmin = currentRole === 'owner'

  const workspaceQuery = useWorkspaceDetail(workspaceId)
  const membersQuery = useWorkspaceMembers(workspaceId)
  const invitesQuery = useWorkspaceInvites(workspaceId, canManageWorkspace)
  const projectAccessQuery = useProjectsForAccessManagement(workspaceId, canManageWorkspace)
  const updateWorkspace = useUpdateWorkspace()
  const createInvite = useCreateInvite()
  const removeMember = useRemoveWorkspaceMember()
  const cancelInvite = useCancelWorkspaceInvite()
  const grantAccess = useGrantProjectAccess()
  const revokeAccess = useRevokeProjectAccess()

  const workspace = workspaceQuery.data
  const members = membersQuery.data ?? []
  const invites = invitesQuery.data ?? []
  const projects = projectAccessQuery.data ?? []
  const pendingInvites = invites.filter((invite) => invite.status === 'pending')
  const inviteHistory = invites.filter((invite) => invite.status !== 'pending')

  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [showInvite, setShowInvite] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<'member' | 'admin'>('member')
  const [inviteProjectIds, setInviteProjectIds] = useState<string[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | undefined>()
  const [memberToRemove, setMemberToRemove] = useState<Member | null>(null)

  const rosterQuery = useProjectMembers(selectedProjectId)
  const selectedProject = projects.find((project) => project.id === selectedProjectId)
  const roster = rosterQuery.data?.subjects ?? []

  useEffect(() => {
    if (!workspace) return
    setName(workspace.name)
    setSlug(workspace.slug)
    if (currentWorkspace?.id !== workspace.id) selectWorkspace({ id: workspace.id, name: workspace.name, slug: workspace.slug })
  }, [currentWorkspace?.id, workspace, selectWorkspace])

  useEffect(() => {
    if (!selectedProjectId && projects.length > 0) setSelectedProjectId(projects[0].id)
    if (selectedProjectId && !projects.some((project) => project.id === selectedProjectId)) setSelectedProjectId(projects[0]?.id)
  }, [projects, selectedProjectId])

  const peopleCount = members.length + pendingInvites.length
  const projectCount = canManageWorkspace ? projects.length : currentWorkspace?.accessible_project_count ?? 0
  const explicitProjectAccesses = useMemo(
    () => members
      .filter((member) => member.access_mode !== 'implicit_owner')
      .reduce((total, member) => total + Number(member.project_access_count || 0), 0),
    [members],
  )

  const handleSave = async () => {
    if (!workspaceId || !canManageWorkspace) return
    try {
      const updated = await updateWorkspace.mutateAsync({ id: workspaceId, data: { name: name.trim(), slug: slug.trim() } })
      selectWorkspace({ ...currentWorkspace!, id: updated.id, name: updated.name, slug: updated.slug })
      toast.success('Workspace updated')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Workspace')
    }
  }

  const toggleInviteProject = (projectId: string) => {
    setInviteProjectIds((current) => current.includes(projectId) ? current.filter((id) => id !== projectId) : [...current, projectId])
  }

  const handleInvite = async () => {
    if (!workspaceId || !inviteEmail.trim()) return
    try {
      await createInvite.mutateAsync({
        workspaceId: workspaceId,
        data: { email: inviteEmail.trim(), role: inviteRole, project_ids: inviteProjectIds },
      })
      toast.success('Invitation created')
      setShowInvite(false)
      setInviteEmail('')
      setInviteRole('member')
      setInviteProjectIds([])
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create invitation')
    }
  }

  const handleRemoveMember = async () => {
    if (!workspaceId || !memberToRemove) return
    try {
      const result = await removeMember.mutateAsync({ workspaceId: workspaceId, userId: memberToRemove.user_id })
      toast.success('Member removed', { description: `${result.project_accesses_removed} Project access(es) revoked.` })
      setMemberToRemove(null)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to remove member')
    }
  }

  const handleCancelInvite = async (invite: Invite) => {
    if (!workspaceId) return
    try {
      await cancelInvite.mutateAsync({ workspaceId: workspaceId, inviteId: invite.id })
      toast.success('Invitation cancelled')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to cancel invitation')
    }
  }

  const handleAccess = async (subject: ProjectAccessSubject) => {
    if (!selectedProjectId || subject.project_access === 'implicit') return
    try {
      if (subject.project_access === 'active' || subject.project_access === 'pending') {
        await revokeAccess.mutateAsync({ projectId: selectedProjectId, subjectType: subject.subject_type, subjectId: subject.subject_id })
        toast.success(subject.subject_type === 'invite' ? 'Prepared access removed' : 'Project access removed')
      } else {
        await grantAccess.mutateAsync({ projectId: selectedProjectId, subjectType: subject.subject_type, subjectId: subject.subject_id })
        toast.success(subject.subject_type === 'invite' ? 'Access will be applied after acceptance' : 'Project access granted')
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Project access')
    }
  }

  if (workspaceQuery.isLoading) return <LoadingState />
  if (workspaceQuery.isError) return <ErrorState error={workspaceQuery.error} onRetry={workspaceQuery.refetch} />
  if (!workspace) return <ErrorState message="Workspace not found" />

  const overview = (
    <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
      <Card>
        <CardHeader><CardTitle>Workspace details</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div><label className="mb-1.5 block text-xs font-medium text-muted">Name</label><Input value={name} onChange={(event) => setName(event.target.value)} disabled={!canManageWorkspace} /></div>
          <div><label className="mb-1.5 block text-xs font-medium text-muted">Slug</label><Input value={slug} onChange={(event) => setSlug(event.target.value)} disabled={!canManageWorkspace} /></div>
          <div className="grid gap-3 rounded-xl border border-border bg-background/35 p-4 text-xs text-muted sm:grid-cols-2"><span>ID<br /><code className="text-slate-300">{workspace.id}</code></span><span>Created<br /><strong className="font-medium text-slate-300">{formatDate(workspace.created_at)}</strong></span></div>
          {canManageWorkspace ? <div className="flex justify-end"><Button onClick={handleSave} loading={updateWorkspace.isPending}>Save changes</Button></div> : <p className="text-xs text-muted">Workspace details are read-only for your role.</p>}
        </CardContent>
      </Card>
      <div className="space-y-4">
        <Card><CardHeader><CardTitle>Operating model</CardTitle></CardHeader><CardContent className="space-y-3 text-sm text-muted"><p><strong className="text-white">Workspace</strong> owns plan, people and limits.</p><p><strong className="text-white">Projects</strong> isolate Agents, Knowledge, Tools, runtime and observability.</p><p><strong className="text-white">Project access</strong> is binary in the MVP.</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Quick actions</CardTitle></CardHeader><CardContent className="grid gap-2"><Button variant="outline" onClick={() => navigate(`/workspaces/${workspaceId}/projects`)}><FolderKanban className="mr-2 h-4 w-4" />Open Projects</Button><Button variant="outline" onClick={() => navigate(`/workspaces/${workspaceId}/billing`)}><CreditCard className="mr-2 h-4 w-4" />Open Billing</Button>{canManageWorkspace && <Button onClick={() => setShowInvite(true)}><UserPlus className="mr-2 h-4 w-4" />Invite member</Button>}</CardContent></Card>
      </div>
    </div>
  )

  const people = (
    <div className="space-y-5">
      <Card>
        <CardHeader><div className="flex items-center justify-between gap-3"><div><CardTitle>People</CardTitle><p className="mt-1 text-xs text-muted">Active memberships and invitations awaiting acceptance.</p></div>{canManageWorkspace && <Button size="sm" onClick={() => setShowInvite(true)}><UserPlus className="mr-2 h-4 w-4" />Invite</Button>}</div></CardHeader>
        <CardContent className="space-y-2">
          {members.map((member) => (
            <div key={member.id} className="flex items-center gap-3 rounded-xl border border-border bg-background/30 p-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary-light">{initials(member.email)}</div>
              <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-white">{member.email}</p><p className="mt-0.5 text-xs text-muted">{member.access_mode === 'implicit_owner' ? 'All Projects · implicit access' : `${member.project_access_count} assigned Project(s)`}</p></div>
              <StatusBadge status={member.role} /><StatusBadge status="active" />
              {canManageWorkspace && member.role !== 'owner' && !(currentRole === 'admin' && member.role === 'admin') && <Button size="sm" variant="outline" onClick={() => setMemberToRemove(member)}><UserMinus className="mr-1 h-3.5 w-3.5" />Remove</Button>}
            </div>
          ))}
          {pendingInvites.map((invite) => (
            <div key={invite.id} className="flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-500/10 text-amber-200"><Mail className="h-4 w-4" /></div>
              <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-white">{invite.email}</p><p className="mt-0.5 text-xs text-muted">{invite.project_count} Project(s) prepared · expires {formatDate(invite.expires_at)}</p></div>
              <StatusBadge status={invite.role} /><StatusBadge status="pending" />
              <Button size="sm" variant="outline" onClick={() => handleCancelInvite(invite)} disabled={cancelInvite.isPending}>Cancel</Button>
            </div>
          ))}
          {peopleCount === 0 && <p className="py-8 text-center text-sm text-muted">No people found.</p>}
        </CardContent>
      </Card>
      {inviteHistory.length > 0 && <details className="rounded-xl border border-border bg-surface/50"><summary className="cursor-pointer px-4 py-3 text-sm font-medium text-muted">Invitation history · {inviteHistory.length}</summary><div className="space-y-2 border-t border-border p-4">{inviteHistory.map((invite) => <div key={invite.id} className="flex items-center justify-between gap-3 text-xs"><span className="truncate text-slate-300">{invite.email}</span><span className="flex items-center gap-2"><StatusBadge status={invite.role} /><StatusBadge status={invite.status} /></span></div>)}</div></details>}
    </div>
  )

  const projectAccess = (
    canManageWorkspace ? (
      <div className="grid min-h-[480px] overflow-hidden rounded-xl border border-border bg-surface/50 lg:grid-cols-[280px_1fr]">
        <aside className="border-b border-border p-3 lg:border-b-0 lg:border-r">
          <div className="px-2 pb-3"><p className="text-sm font-semibold text-white">Projects</p><p className="mt-1 text-xs text-muted">Choose a Project to manage full access.</p></div>
          <div className="space-y-1">{projects.map((project) => <button key={project.id} type="button" onClick={() => setSelectedProjectId(project.id)} className={`w-full rounded-lg border px-3 py-3 text-left ${selectedProjectId === project.id ? 'border-primary/40 bg-primary/10' : 'border-transparent hover:border-border hover:bg-background/40'}`}><span className="block truncate text-sm font-medium text-white">{project.name}</span><span className="mt-1 block text-xs text-muted">{project.member_count} active · {project.pending_count} pending</span></button>)}</div>
        </aside>
        <section className="min-w-0 p-4">
          <div className="mb-4"><p className="text-sm font-semibold text-white">{selectedProject ? `Access to ${selectedProject.name}` : 'Select a Project'}</p><p className="mt-1 text-xs text-muted">Owner access is implicit. Member access is explicit. Pending invitations can be prepared before acceptance.</p></div>
          {rosterQuery.isLoading ? <LoadingState message="Loading access roster" variant="panel" /> : selectedProject ? <div className="space-y-2">{roster.map((subject) => {
            const enabled = subject.project_access !== 'none'
            const locked = subject.project_access === 'implicit'
            return <div key={`${subject.subject_type}:${subject.subject_id}`} className="flex items-center gap-3 rounded-xl border border-border bg-background/30 p-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary-light">{subject.subject_type === 'invite' ? <Mail className="h-4 w-4" /> : initials(subject.email)}</div><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-white">{subject.email}</p><p className="mt-0.5 text-xs text-muted">{subject.subject_type === 'invite' ? 'Invitation pending' : `${subject.workspace_role} · active member`}</p></div><StatusBadge status={subject.workspace_role} /><button type="button" disabled={locked || grantAccess.isPending || revokeAccess.isPending} onClick={() => handleAccess(subject)} className={`min-w-28 rounded-lg border px-3 py-2 text-xs font-medium ${locked ? 'cursor-not-allowed border-primary/20 bg-primary/10 text-primary-light' : enabled ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' : 'border-border bg-background/50 text-muted hover:border-primary/30 hover:text-white'}`}>{locked ? 'Implicit' : subject.project_access === 'pending' ? 'On acceptance' : subject.project_access === 'active' ? 'Enabled' : 'No access'}</button></div>
          })}</div> : <p className="text-sm text-muted">No Projects available.</p>}
        </section>
      </div>
    ) : <Card><CardContent className="py-12 text-center"><ShieldCheck className="mx-auto h-8 w-8 text-muted" /><p className="mt-3 text-sm font-medium text-white">Project access management is restricted</p><p className="mt-1 text-xs text-muted">Only Workspace owners and admins can manage Project access.</p></CardContent></Card>
  )

  return (
    <div className="space-y-5">
      <PageHeader
        title={workspace.name}
        description={`/${workspace.slug} · Workspace`}
        actions={<div className="flex items-center gap-2"><Button variant="outline" onClick={() => navigate('/workspaces')}><ArrowLeft className="mr-2 h-4 w-4" />Workspaces</Button><Button onClick={() => navigate(`/workspaces/${workspaceId}/projects`)}>Open Projects</Button></div>}
      />

      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface/60 px-4 py-3"><Building2 className="h-4 w-4 text-primary-light" /><span className="text-sm font-medium text-white">{workspace.name}</span><StatusBadge status={currentRole} /><StatusBadge status={workspace.status} /><span className="ml-auto text-xs text-muted">Commercial workspace · Project isolation boundary</span></div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="People" value={peopleCount} detail={`${members.length} active · ${pendingInvites.length} pending`} icon={<Users className="h-4 w-4" />} />
        <SummaryCard label="Projects" value={projectCount} detail="Accessible technical boundaries" icon={<FolderKanban className="h-4 w-4" />} />
        <SummaryCard label="Access grants" value={explicitProjectAccesses} detail="Active explicit assignments" icon={<ShieldCheck className="h-4 w-4" />} />
        <SummaryCard label="Role" value={currentRole.toUpperCase()} detail={canManageWorkspace ? 'Workspace management' : 'Read-only Workspace view'} icon={<Building2 className="h-4 w-4" />} />
      </div>

      <Tabs tabs={[{ id: 'overview', label: 'Overview', content: overview }, { id: 'people', label: `People (${peopleCount})`, content: people }, { id: 'access', label: 'Project Access', content: projectAccess }]} />

      <Dialog open={showInvite && canManageWorkspace} onClose={() => setShowInvite(false)} title="Invite member" className="max-w-xl" scrollMode="content">
        <div className="space-y-5">
          <div><label className="mb-1.5 block text-xs font-medium text-muted">Email</label><Input type="email" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} placeholder="person@company.com" /></div>
          <div className="space-y-2"><p className="text-xs font-medium text-muted">Workspace role</p><RoleChoice active={inviteRole === 'member'} title="Member" description="Can operate only Projects explicitly assigned to this person." onClick={() => setInviteRole('member')} />{canInviteAdmin && <RoleChoice active={inviteRole === 'admin'} title="Admin" description="Can manage the Workspace and Project access, but still needs explicit access to operate a Project." onClick={() => setInviteRole('admin')} />}</div>
          <div><div className="mb-2"><p className="text-xs font-medium text-muted">Project access after acceptance</p><p className="mt-1 text-xs text-muted">Optional. Selected Projects become available immediately when the invitation is accepted.</p></div><div className="max-h-48 space-y-2 overflow-y-auto rounded-xl border border-border bg-background/30 p-2">{projects.length ? projects.map((project) => <label key={project.id} className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 hover:bg-surface/70"><input type="checkbox" checked={inviteProjectIds.includes(project.id)} onChange={() => toggleInviteProject(project.id)} className="h-4 w-4 rounded border-border accent-blue-500" /><span className="min-w-0"><span className="block truncate text-sm text-white">{project.name}</span><span className="block truncate text-xs text-muted">/{project.slug}</span></span></label>) : <p className="p-3 text-xs text-muted">No Projects available.</p>}</div></div>
          <div className="rounded-xl border border-border bg-background/35 p-3 text-xs text-muted">{inviteProjectIds.length ? `${inviteProjectIds.length} Project access grant(s) will be prepared.` : 'The person will join the Workspace without Project access.'}</div>
          <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setShowInvite(false)}>Cancel</Button><Button onClick={handleInvite} loading={createInvite.isPending} disabled={!inviteEmail.trim()}>Send invitation</Button></div>
        </div>
      </Dialog>

      <Dialog open={Boolean(memberToRemove)} onClose={() => setMemberToRemove(null)} title="Remove member from Workspace?">
        <div className="space-y-4"><p className="text-sm text-muted"><strong className="text-white">{memberToRemove?.email}</strong> will lose access to this Workspace.</p><div className="rounded-xl border border-red-500/20 bg-red-500/[0.05] p-4 text-xs leading-5 text-red-100"><p>{memberToRemove?.project_access_count ?? 0} active Project access(es) will be revoked.</p><p>Pending access grants for this email will be cancelled.</p><p>Historical traces, releases and audit data remain unchanged.</p></div><div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setMemberToRemove(null)}>Cancel</Button><Button variant="destructive" onClick={handleRemoveMember} loading={removeMember.isPending}>Remove member</Button></div></div>
      </Dialog>
    </div>
  )
}
