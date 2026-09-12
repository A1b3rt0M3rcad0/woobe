import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Building2, Check, FolderKanban, Mail, ShieldCheck, UserMinus, UserPlus, Users } from 'lucide-react'
import { Badge, Button, Card, Dialog, Input, type BadgeVariant } from '@woobe/ui'
import { toast } from 'sonner'

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

type SettingsTab = 'overview' | 'people' | 'access'
type SettingsView = 'main' | 'invite' | 'remove'

interface WorkspaceSettingsDialogProps {
  open: boolean
  onClose: () => void
  workspaceId: string
}

function formatDate(value?: string | null) {
  if (!value) return 'Not recorded'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Invalid date'
  return new Intl.DateTimeFormat('en-US', { day: '2-digit', month: 'short', year: 'numeric' }).format(date)
}

function initials(email: string) {
  return email.split('@')[0].split(/[._-]/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'U'
}

function badgeVariant(status?: string): BadgeVariant {
  if (status === 'owner') return 'default'
  if (status === 'admin' || status === 'active') return 'success'
  if (status === 'pending') return 'warning'
  return 'outline'
}

function SummaryMetric({ label, value, detail, icon }: { label: string; value: string | number; detail: string; icon: ReactNode }) {
  return (
    <Card className="p-3.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[8px] font-bold uppercase tracking-[0.12em] text-muted">{label}</p>
          <p className="mt-1.5 font-mono text-base font-bold text-slate-50">{value}</p>
          <p className="mt-1 truncate font-mono text-[8px] text-muted-foreground">{detail}</p>
        </div>
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">
          {icon}
        </div>
      </div>
    </Card>
  )
}

function RoleChoice({ active, title, description, onClick }: { active: boolean; title: string; description: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full rounded-container border p-3 text-left transition-colors ${active ? 'border-primary/45 bg-primary/[0.08]' : 'border-border bg-control/35 hover:border-slate-600'}`}
    >
      <span className="flex items-start gap-2.5">
        <span className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-technical border ${active ? 'border-primary bg-primary text-white' : 'border-border text-transparent'}`}>
          <Check className="h-2.5 w-2.5" />
        </span>
        <span className="min-w-0">
          <span className="block font-mono text-[10px] font-bold text-slate-100">{title}</span>
          <span className="mt-1 block font-mono text-[8px] leading-4 text-muted-foreground">{description}</span>
        </span>
      </span>
    </button>
  )
}

export function WorkspaceSettingsDialog({ open, onClose, workspaceId }: WorkspaceSettingsDialogProps) {
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

  const [tab, setTab] = useState<SettingsTab>('overview')
  const [view, setView] = useState<SettingsView>('main')
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
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
  }, [workspace])

  useEffect(() => {
    if (!selectedProjectId && projects.length > 0) setSelectedProjectId(projects[0].id)
    if (selectedProjectId && !projects.some((project) => project.id === selectedProjectId)) setSelectedProjectId(projects[0]?.id)
  }, [projects, selectedProjectId])

  useEffect(() => {
    if (!open) {
      setTab('overview')
      setView('main')
      setMemberToRemove(null)
      setInviteEmail('')
      setInviteRole('member')
      setInviteProjectIds([])
    }
  }, [open])

  const peopleCount = members.length + pendingInvites.length
  const projectCount = canManageWorkspace ? projects.length : currentWorkspace?.accessible_project_count ?? 0
  const explicitProjectAccesses = useMemo(
    () => members
      .filter((member) => member.access_mode !== 'implicit_owner')
      .reduce((total, member) => total + Number(member.project_access_count || 0), 0),
    [members],
  )

  const handleSave = async () => {
    if (!canManageWorkspace) return
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
    if (!inviteEmail.trim()) return
    try {
      await createInvite.mutateAsync({
        workspaceId,
        data: { email: inviteEmail.trim(), role: inviteRole, project_ids: inviteProjectIds },
      })
      toast.success('Invitation created')
      setInviteEmail('')
      setInviteRole('member')
      setInviteProjectIds([])
      setView('main')
      setTab('people')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create invitation')
    }
  }

  const handleRemoveMember = async () => {
    if (!memberToRemove) return
    try {
      const result = await removeMember.mutateAsync({ workspaceId, userId: memberToRemove.user_id })
      toast.success('Member removed', { description: `${result.project_accesses_removed} Project access(es) revoked.` })
      setMemberToRemove(null)
      setView('main')
      setTab('people')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to remove member')
    }
  }

  const handleCancelInvite = async (invite: Invite) => {
    try {
      await cancelInvite.mutateAsync({ workspaceId, inviteId: invite.id })
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

  const openInvite = () => {
    setView('invite')
  }

  const openRemove = (member: Member) => {
    setMemberToRemove(member)
    setView('remove')
  }

  const backToMain = () => {
    setView('main')
    setMemberToRemove(null)
  }

  const overview = workspace ? (
    <div className="grid gap-3 lg:grid-cols-[1.15fr_0.85fr]">
      <Card className="p-4">
        <div className="mb-4 border-b border-border pb-3">
          <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-slate-100">Workspace details</h3>
        </div>
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block font-mono text-[9px] font-medium text-slate-300">Name</label>
            <Input value={name} onChange={(event) => setName(event.target.value)} disabled={!canManageWorkspace} />
          </div>
          <div>
            <label className="mb-1.5 block font-mono text-[9px] font-medium text-slate-300">Slug</label>
            <Input value={slug} onChange={(event) => setSlug(event.target.value)} disabled={!canManageWorkspace} className="font-mono text-[10px]" />
          </div>
          <div className="grid gap-px overflow-hidden rounded-container border border-border bg-border sm:grid-cols-2">
            <div className="bg-control/70 p-3">
              <span className="block font-mono text-[8px] uppercase tracking-[0.1em] text-muted">ID</span>
              <code className="mt-1 block truncate font-mono text-[9px] text-slate-300">{workspace.id}</code>
            </div>
            <div className="bg-control/70 p-3">
              <span className="block font-mono text-[8px] uppercase tracking-[0.1em] text-muted">Created</span>
              <strong className="mt-1 block font-mono text-[9px] font-medium text-slate-300">{formatDate(workspace.created_at)}</strong>
            </div>
          </div>
          {canManageWorkspace ? (
            <div className="flex justify-end border-t border-border pt-4">
              <Button onClick={handleSave} loading={updateWorkspace.isPending}>Save changes</Button>
            </div>
          ) : (
            <p className="font-mono text-[9px] text-muted-foreground">Workspace details are read-only for your role.</p>
          )}
        </div>
      </Card>

      <Card className="p-4">
        <div className="mb-4 border-b border-border pb-3">
          <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-slate-100">Operating model</h3>
        </div>
        <div className="space-y-3 font-mono text-[9px] leading-4 text-muted-foreground">
          <p><strong className="font-medium text-slate-100">Workspace</strong> owns plan, people and limits.</p>
          <p><strong className="font-medium text-slate-100">Projects</strong> isolate Agents, Knowledge, Tools, runtime and observability.</p>
          <p><strong className="font-medium text-slate-100">Project access</strong> is binary in the MVP.</p>
        </div>
      </Card>
    </div>
  ) : null

  const people = (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-slate-100">People</h3>
          <p className="mt-1 font-mono text-[8px] text-muted-foreground">Active memberships and invitations awaiting acceptance.</p>
        </div>
        {canManageWorkspace && <Button size="sm" onClick={openInvite}><UserPlus className="h-3 w-3" />Invite</Button>}
      </div>

      <div className="overflow-hidden rounded-container border border-border bg-surface">
        {members.map((member) => (
          <div key={member.id} className="flex flex-wrap items-center gap-3 border-b border-border px-3 py-2.5 last:border-b-0">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control font-mono text-[9px] font-bold text-primary-light">{initials(member.email)}</div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-[10px] font-medium text-slate-100">{member.email}</p>
              <p className="mt-0.5 truncate font-mono text-[8px] text-muted-foreground">{member.access_mode === 'implicit_owner' ? 'All Projects · implicit access' : `${member.project_access_count} assigned Project(s)`}</p>
            </div>
            <Badge variant={badgeVariant(member.role)} className="font-mono text-[8px] uppercase">{member.role}</Badge>
            <Badge variant="success" className="font-mono text-[8px] uppercase">active</Badge>
            {canManageWorkspace && member.role !== 'owner' && !(currentRole === 'admin' && member.role === 'admin') && (
              <Button size="sm" variant="outline" onClick={() => openRemove(member)}><UserMinus className="h-3 w-3" />Remove</Button>
            )}
          </div>
        ))}
        {pendingInvites.map((invite) => (
          <div key={invite.id} className="flex flex-wrap items-center gap-3 border-b border-border bg-warning/[0.025] px-3 py-2.5 last:border-b-0">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-amber-500/20 bg-amber-500/[0.06] text-amber-200"><Mail className="h-3.5 w-3.5" /></div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-[10px] font-medium text-slate-100">{invite.email}</p>
              <p className="mt-0.5 truncate font-mono text-[8px] text-muted-foreground">{invite.project_count} Project(s) prepared · expires {formatDate(invite.expires_at)}</p>
            </div>
            <Badge variant={badgeVariant(invite.role)} className="font-mono text-[8px] uppercase">{invite.role}</Badge>
            <Badge variant="warning" className="font-mono text-[8px] uppercase">pending</Badge>
            <Button size="sm" variant="outline" onClick={() => handleCancelInvite(invite)} disabled={cancelInvite.isPending}>Cancel</Button>
          </div>
        ))}
        {peopleCount === 0 && <p className="py-10 text-center font-mono text-[9px] text-muted-foreground">No people found.</p>}
      </div>

      {inviteHistory.length > 0 && (
        <details className="rounded-container border border-border bg-control/25">
          <summary className="cursor-pointer px-3 py-2.5 font-mono text-[9px] text-muted-foreground">Invitation history · {inviteHistory.length}</summary>
          <div className="border-t border-border">
            {inviteHistory.map((invite) => (
              <div key={invite.id} className="flex items-center justify-between gap-3 border-b border-border px-3 py-2 last:border-b-0">
                <span className="truncate font-mono text-[9px] text-slate-300">{invite.email}</span>
                <span className="flex items-center gap-2">
                  <Badge variant={badgeVariant(invite.role)} className="font-mono text-[8px] uppercase">{invite.role}</Badge>
                  <Badge variant={badgeVariant(invite.status)} className="font-mono text-[8px] uppercase">{invite.status}</Badge>
                </span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )

  const projectAccess = canManageWorkspace ? (
    <div className="grid min-h-[390px] overflow-hidden rounded-container border border-border bg-surface lg:grid-cols-[240px_1fr]">
      <aside className="border-b border-border bg-control/20 p-3 lg:border-b-0 lg:border-r">
        <div className="px-1 pb-3">
          <p className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-slate-100">Projects</p>
          <p className="mt-1 font-mono text-[8px] leading-4 text-muted-foreground">Choose a Project to manage full access.</p>
        </div>
        <div className="grid gap-[3px]">
          {projects.map((project) => (
            <button
              key={project.id}
              type="button"
              onClick={() => setSelectedProjectId(project.id)}
              className={`w-full rounded-control border px-2.5 py-2 text-left transition-colors ${selectedProjectId === project.id ? 'border-primary/40 bg-primary/[0.08]' : 'border-transparent hover:border-border hover:bg-control'}`}
            >
              <span className="block truncate font-mono text-[10px] font-medium text-slate-100">{project.name}</span>
              <span className="mt-0.5 block font-mono text-[8px] text-muted-foreground">{project.member_count} active · {project.pending_count} pending</span>
            </button>
          ))}
        </div>
      </aside>
      <section className="min-w-0 p-3.5">
        <div className="mb-3 border-b border-border pb-3">
          <p className="font-mono text-[10px] font-bold text-slate-100">{selectedProject ? `Access to ${selectedProject.name}` : 'Select a Project'}</p>
          <p className="mt-1 font-mono text-[8px] leading-4 text-muted-foreground">Owner access is implicit. Member access is explicit. Pending invitations can be prepared before acceptance.</p>
        </div>
        {rosterQuery.isLoading ? (
          <p className="py-8 text-center font-mono text-[9px] text-muted-foreground">Loading access roster...</p>
        ) : selectedProject ? (
          <div className="overflow-hidden rounded-container border border-border">
            {roster.map((subject) => {
              const enabled = subject.project_access !== 'none'
              const locked = subject.project_access === 'implicit'
              const label = locked ? 'Implicit' : subject.project_access === 'pending' ? 'On acceptance' : subject.project_access === 'active' ? 'Enabled' : 'No access'
              return (
                <div key={`${subject.subject_type}:${subject.subject_id}`} className="flex flex-wrap items-center gap-3 border-b border-border bg-control/20 px-3 py-2.5 last:border-b-0">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control font-mono text-[9px] font-bold text-primary-light">{subject.subject_type === 'invite' ? <Mail className="h-3.5 w-3.5" /> : initials(subject.email)}</div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-mono text-[10px] font-medium text-slate-100">{subject.email}</p>
                    <p className="mt-0.5 truncate font-mono text-[8px] text-muted-foreground">{subject.subject_type === 'invite' ? 'Invitation pending' : `${subject.workspace_role} · active member`}</p>
                  </div>
                  <Badge variant={badgeVariant(subject.workspace_role)} className="font-mono text-[8px] uppercase">{subject.workspace_role}</Badge>
                  <button
                    type="button"
                    disabled={locked || grantAccess.isPending || revokeAccess.isPending}
                    onClick={() => handleAccess(subject)}
                    className={`min-w-24 rounded-control border px-2.5 py-1.5 font-mono text-[8px] font-medium transition-colors disabled:cursor-not-allowed ${locked ? 'border-primary/20 bg-primary/[0.08] text-primary-light' : enabled ? 'border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-300' : 'border-border bg-control text-muted-foreground hover:border-slate-600 hover:text-slate-100'}`}
                  >
                    {label}
                  </button>
                </div>
              )
            })}
            {roster.length === 0 && <p className="py-8 text-center font-mono text-[9px] text-muted-foreground">No access subjects found.</p>}
          </div>
        ) : (
          <p className="py-8 text-center font-mono text-[9px] text-muted-foreground">No Projects available.</p>
        )}
      </section>
    </div>
  ) : (
    <Card className="px-6 py-10 text-center">
      <ShieldCheck className="mx-auto h-5 w-5 text-muted-foreground" />
      <p className="mt-3 font-mono text-[10px] font-bold text-slate-100">Project access management is restricted</p>
      <p className="mt-1 font-mono text-[8px] text-muted-foreground">Only Workspace owners and admins can manage Project access.</p>
    </Card>
  )

  const mainView = workspace ? (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2 border-b border-border pb-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-control border border-border bg-control text-primary-light">
          <Building2 className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <p className="truncate font-mono text-[11px] font-bold text-slate-100">{workspace.name}</p>
          <p className="mt-0.5 truncate font-mono text-[8px] text-muted-foreground">/{workspace.slug}</p>
        </div>
        <Badge variant={badgeVariant(currentRole)} className="font-mono text-[8px] uppercase">{currentRole}</Badge>
        {workspace.status && <Badge variant={badgeVariant(workspace.status)} className="font-mono text-[8px] uppercase">{workspace.status}</Badge>}
      </div>

      <div className="mb-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryMetric label="People" value={peopleCount} detail={`${members.length} active · ${pendingInvites.length} pending`} icon={<Users className="h-3.5 w-3.5" />} />
        <SummaryMetric label="Projects" value={projectCount} detail="Accessible boundaries" icon={<FolderKanban className="h-3.5 w-3.5" />} />
        <SummaryMetric label="Access grants" value={explicitProjectAccesses} detail="Explicit assignments" icon={<ShieldCheck className="h-3.5 w-3.5" />} />
        <SummaryMetric label="Role" value={currentRole.toUpperCase()} detail={canManageWorkspace ? 'Workspace management' : 'Read-only view'} icon={<Building2 className="h-3.5 w-3.5" />} />
      </div>

      <div className="mb-4 flex gap-1 border-b border-border" role="tablist" aria-label="Workspace settings">
        {([
          ['overview', 'Overview'],
          ['people', `People (${peopleCount})`],
          ['access', 'Project Access'],
        ] as Array<[SettingsTab, string]>).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={`border-b px-3 py-2 font-mono text-[9px] font-medium transition-colors ${tab === value ? 'border-primary text-primary-light' : 'border-transparent text-muted-foreground hover:text-slate-200'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'overview' && overview}
      {tab === 'people' && people}
      {tab === 'access' && projectAccess}
    </div>
  ) : null

  const inviteView = (
    <div className="space-y-4">
      <div className="border-b border-border pb-3">
        <p className="font-mono text-[10px] font-bold text-slate-100">Invite member</p>
        <p className="mt-1 font-mono text-[8px] text-muted-foreground">Configure Workspace role and optional Project access.</p>
      </div>
      <div>
        <label className="mb-1.5 block font-mono text-[9px] font-medium text-slate-300">Email</label>
        <Input type="email" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} placeholder="person@company.com" />
      </div>
      <div className="space-y-2">
        <p className="font-mono text-[9px] font-medium text-slate-300">Workspace role</p>
        <RoleChoice active={inviteRole === 'member'} title="Member" description="Can operate only Projects explicitly assigned to this person." onClick={() => setInviteRole('member')} />
        {canInviteAdmin && <RoleChoice active={inviteRole === 'admin'} title="Admin" description="Can manage the Workspace and Project access, but still needs explicit access to operate a Project." onClick={() => setInviteRole('admin')} />}
      </div>
      <div>
        <div className="mb-2">
          <p className="font-mono text-[9px] font-medium text-slate-300">Project access after acceptance</p>
          <p className="mt-1 font-mono text-[8px] text-muted-foreground">Optional. Selected Projects become available immediately when the invitation is accepted.</p>
        </div>
        <div className="max-h-48 overflow-y-auto rounded-container border border-border bg-control/25 p-1.5">
          {projects.length ? projects.map((project) => (
            <label key={project.id} className="flex cursor-pointer items-center gap-2.5 rounded-control px-2.5 py-2 hover:bg-control">
              <input type="checkbox" checked={inviteProjectIds.includes(project.id)} onChange={() => toggleInviteProject(project.id)} className="h-3.5 w-3.5 rounded-technical border-border accent-blue-500" />
              <span className="min-w-0">
                <span className="block truncate font-mono text-[9px] text-slate-100">{project.name}</span>
                <span className="block truncate font-mono text-[8px] text-muted-foreground">/{project.slug}</span>
              </span>
            </label>
          )) : <p className="p-3 font-mono text-[9px] text-muted-foreground">No Projects available.</p>}
        </div>
      </div>
      <div className="rounded-container border border-border bg-control/35 p-3 font-mono text-[8px] text-muted-foreground">
        {inviteProjectIds.length ? `${inviteProjectIds.length} Project access grant(s) will be prepared.` : 'The person will join the Workspace without Project access.'}
      </div>
      <div className="flex justify-end gap-2 border-t border-border pt-4">
        <Button variant="outline" onClick={backToMain}>Cancel</Button>
        <Button onClick={handleInvite} loading={createInvite.isPending} disabled={!inviteEmail.trim()}>Send invitation</Button>
      </div>
    </div>
  )

  const removeView = (
    <div className="space-y-4">
      <div>
        <p className="font-mono text-[10px] font-bold text-slate-100">Remove member from Workspace?</p>
        <p className="mt-2 font-mono text-[9px] leading-4 text-muted-foreground"><strong className="font-medium text-slate-100">{memberToRemove?.email}</strong> will lose access to this Workspace.</p>
      </div>
      <div className="rounded-container border border-red-500/20 bg-red-500/[0.04] p-3 font-mono text-[8px] leading-4 text-red-100">
        <p>{memberToRemove?.project_access_count ?? 0} active Project access(es) will be revoked.</p>
        <p>Pending access grants for this email will be cancelled.</p>
        <p>Historical traces, releases and audit data remain unchanged.</p>
      </div>
      <div className="flex justify-end gap-2 border-t border-border pt-4">
        <Button variant="outline" onClick={backToMain}>Cancel</Button>
        <Button variant="destructive" onClick={handleRemoveMember} loading={removeMember.isPending}>Remove member</Button>
      </div>
    </div>
  )

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={view === 'main' ? 'Workspace settings' : view === 'invite' ? 'Invite member' : 'Remove member'}
      className="max-w-[980px]"
      contentClassName="max-h-[calc(100svh-7rem)] overflow-y-auto p-4 sm:p-5"
    >
      {workspaceQuery.isLoading ? (
        <div className="py-14 text-center font-mono text-[9px] text-muted-foreground">Loading Workspace...</div>
      ) : workspaceQuery.isError ? (
        <Card className="border-error/30 bg-error/[0.05] px-6 py-10 text-center">
          <p className="font-mono text-[10px] font-bold text-red-200">Unable to load Workspace</p>
          <p className="mt-1 font-mono text-[8px] text-red-200/70">{workspaceQuery.error instanceof Error ? workspaceQuery.error.message : 'Unknown error'}</p>
        </Card>
      ) : !workspace ? (
        <Card className="border-error/30 bg-error/[0.05] px-6 py-10 text-center">
          <p className="font-mono text-[10px] font-bold text-red-200">Workspace not found</p>
        </Card>
      ) : view === 'invite' ? inviteView : view === 'remove' ? removeView : mainView}
    </Dialog>
  )
}
