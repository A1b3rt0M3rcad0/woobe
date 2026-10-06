import { useEffect, useMemo, useState } from 'react'
import { Building2, Check, FolderKanban, Mail, ShieldCheck, UserMinus, UserPlus, Users } from 'lucide-react'
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Checkbox,
  Dialog,
  EmptyStatePanel,
  Field,
  FieldDescription,
  FieldLabel,
  Input,
  MetricTile,
  SectionBlock,
  SegmentedControl,
  Skeleton,
  TechnicalListItem,
  type BadgeVariant,
} from '@woobe/ui'
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
import { WorkspaceCliKeys } from '@/features/control-keys/WorkspaceCliKeys'

type SettingsTab = 'overview' | 'people' | 'access' | 'cli-keys'
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

function PersonGlyph({ email, invite = false }: { email: string; invite?: boolean }) {
  return (
    <span className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-border bg-control font-mono text-system-label font-semibold text-primary-light">
      {invite ? <Mail className="h-icon w-icon" /> : initials(email)}
    </span>
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
  const [configuringCliKey, setConfiguringCliKey] = useState(false)
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
      setConfiguringCliKey(false)
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

  const backToMain = () => {
    setView('main')
    setMemberToRemove(null)
  }

  const overview = workspace ? (
    <div className="grid gap-ui-md lg:grid-cols-2">
      <SectionBlock title="Workspace details" description="Mutable Workspace identity and stable technical metadata.">
        <div className="grid gap-ui-md">
          <Field>
            <FieldLabel>Name</FieldLabel>
            <Input value={name} onChange={(event) => setName(event.target.value)} disabled={!canManageWorkspace} />
          </Field>
          <Field>
            <FieldLabel>Slug</FieldLabel>
            <Input value={slug} onChange={(event) => setSlug(event.target.value)} disabled={!canManageWorkspace} className="font-mono" />
          </Field>
          <div className="grid gap-ui-xs sm:grid-cols-2">
            <TechnicalListItem label="Workspace ID" description={workspace.id} title={workspace.id} />
            <TechnicalListItem label="Created" description={formatDate(workspace.created_at)} />
          </div>
          {canManageWorkspace ? (
            <div className="flex justify-end border-t border-border pt-ui-md">
              <Button onClick={handleSave} loading={updateWorkspace.isPending}>Save changes</Button>
            </div>
          ) : (
            <Alert variant="info">
              <AlertDescription>Workspace details are read-only for your role.</AlertDescription>
            </Alert>
          )}
        </div>
      </SectionBlock>

      <SectionBlock title="Operating model" description="Ownership boundaries used by the current Workspace model.">
        <div className="grid gap-ui-sm">
          <TechnicalListItem label="Workspace" description="Owns plan, people and limits." />
          <TechnicalListItem label="Projects" description="Isolate Agents, Knowledge, Tools, runtime and observability." />
          <TechnicalListItem label="Project access" description="Binary access boundary in the MVP." />
        </div>
      </SectionBlock>
    </div>
  ) : null

  const people = (
    <SectionBlock
      title="People"
      description="Active memberships and invitations awaiting acceptance."
      actions={canManageWorkspace ? (
        <Button size="sm" onClick={() => setView('invite')}><UserPlus className="h-icon w-icon" />Invite</Button>
      ) : undefined}
    >
      <div className="grid gap-ui-xs">
        {members.map((member) => (
          <TechnicalListItem
            key={member.id}
            label={member.email}
            description={member.access_mode === 'implicit_owner' ? 'All Projects · implicit access' : `${member.project_access_count} assigned Project(s)`}
            leading={<PersonGlyph email={member.email} />}
            meta={(
              <>
                <Badge variant={badgeVariant(member.role)} size="compact">{member.role}</Badge>
                <Badge variant="success" size="compact">active</Badge>
              </>
            )}
            trailing={canManageWorkspace && member.role !== 'owner' && !(currentRole === 'admin' && member.role === 'admin') ? (
              <Button size="sm" variant="outline" onClick={() => { setMemberToRemove(member); setView('remove') }}>
                <UserMinus className="h-icon-sm w-icon-sm" />Remove
              </Button>
            ) : undefined}
          />
        ))}

        {pendingInvites.map((invite) => (
          <TechnicalListItem
            key={invite.id}
            label={invite.email}
            description={`${invite.project_count} Project(s) prepared · expires ${formatDate(invite.expires_at)}`}
            leading={<PersonGlyph email={invite.email} invite />}
            meta={(
              <>
                <Badge variant={badgeVariant(invite.role)} size="compact">{invite.role}</Badge>
                <Badge variant="warning" size="compact">pending</Badge>
              </>
            )}
            trailing={(
              <Button size="sm" variant="outline" onClick={() => handleCancelInvite(invite)} disabled={cancelInvite.isPending}>Cancel</Button>
            )}
          />
        ))}

        {peopleCount === 0 ? <EmptyStatePanel compact title="No people found" /> : null}
      </div>

      {inviteHistory.length > 0 ? (
        <details className="group mt-ui-md overflow-hidden rounded-container border border-border bg-background/20">
          <summary className="cursor-pointer px-ui-md py-ui-sm font-mono text-system-label text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40">
            Invitation history · {inviteHistory.length}
          </summary>
          <div className="grid gap-ui-xs border-t border-border p-ui-sm">
            {inviteHistory.map((invite) => (
              <TechnicalListItem
                key={invite.id}
                label={invite.email}
                meta={(
                  <>
                    <Badge variant={badgeVariant(invite.role)} size="compact">{invite.role}</Badge>
                    <Badge variant={badgeVariant(invite.status)} size="compact">{invite.status}</Badge>
                  </>
                )}
              />
            ))}
          </div>
        </details>
      ) : null}
    </SectionBlock>
  )

  const projectAccess = canManageWorkspace ? (
    <div className="overflow-hidden rounded-container border border-border bg-surface lg:flex">
      <aside className="shrink-0 border-b border-border bg-background/20 p-ui-md lg:w-dialog-sidebar lg:border-b-0 lg:border-r">
        <div className="mb-ui-md">
          <h3 className="font-mono text-system-control font-semibold text-accent-foreground">Projects</h3>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Choose a Project to manage full access.</p>
        </div>
        <div className="grid gap-ui-xs">
          {projects.map((project) => (
            <TechnicalListItem
              key={project.id}
              label={project.name}
              description={`${project.member_count} active · ${project.pending_count} pending`}
              selected={selectedProjectId === project.id}
              onClick={() => setSelectedProjectId(project.id)}
            />
          ))}
          {projects.length === 0 ? <EmptyStatePanel compact title="No Projects available" /> : null}
        </div>
      </aside>

      <section className="min-w-0 flex-1 p-ui-md">
        <div className="mb-ui-md border-b border-border pb-ui-md">
          <h3 className="font-mono text-system-control font-semibold text-accent-foreground">
            {selectedProject ? `Access to ${selectedProject.name}` : 'Select a Project'}
          </h3>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">
            Owner access is implicit. Member access is explicit. Pending invitations can be prepared before acceptance.
          </p>
        </div>

        {rosterQuery.isLoading ? (
          <div className="grid gap-ui-xs">
            <Skeleton className="h-control-row w-full" />
            <Skeleton className="h-control-row w-full" />
            <Skeleton className="h-control-row w-full" />
          </div>
        ) : selectedProject ? (
          <div className="grid gap-ui-xs">
            {roster.map((subject) => {
              const enabled = subject.project_access !== 'none'
              const locked = subject.project_access === 'implicit'
              const label = locked ? 'Implicit' : subject.project_access === 'pending' ? 'On acceptance' : subject.project_access === 'active' ? 'Enabled' : 'No access'
              return (
                <TechnicalListItem
                  key={`${subject.subject_type}:${subject.subject_id}`}
                  label={subject.email}
                  description={subject.subject_type === 'invite' ? 'Invitation pending' : `${subject.workspace_role} · active member`}
                  leading={<PersonGlyph email={subject.email} invite={subject.subject_type === 'invite'} />}
                  meta={<Badge variant={badgeVariant(subject.workspace_role)} size="compact">{subject.workspace_role}</Badge>}
                  trailing={locked ? (
                    <Badge variant="default" size="compact">Implicit</Badge>
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      variant={enabled ? 'secondary' : 'outline'}
                      disabled={grantAccess.isPending || revokeAccess.isPending}
                      onClick={() => handleAccess(subject)}
                    >
                      {label}
                    </Button>
                  )}
                />
              )
            })}
            {roster.length === 0 ? <EmptyStatePanel compact title="No access subjects found" /> : null}
          </div>
        ) : (
          <EmptyStatePanel compact title="No Projects available" />
        )}
      </section>
    </div>
  ) : (
    <EmptyStatePanel
      icon={<ShieldCheck className="h-icon-lg w-icon-lg" />}
      title="Project access management is restricted"
      description="Only Workspace owners and admins can manage Project access."
    />
  )

  const mainView = workspace ? (
    <div className="grid gap-ui-md">
      {!configuringCliKey ? <TechnicalListItem
        label={workspace.name}
        description={`/${workspace.slug}`}
        leading={(
          <span className="flex h-control-nav w-control-nav items-center justify-center rounded-control border border-border bg-control text-primary-light">
            <Building2 className="h-icon w-icon" />
          </span>
        )}
        meta={(
          <>
            <Badge variant={badgeVariant(currentRole)} size="compact">{currentRole}</Badge>
            {workspace.status ? <Badge variant={badgeVariant(workspace.status)} size="compact">{workspace.status}</Badge> : null}
          </>
        )}
      /> : null}

      {!configuringCliKey ? <div className="grid gap-ui-xs sm:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="People" value={peopleCount} detail={`${members.length} active · ${pendingInvites.length} pending`} icon={<Users className="h-icon-sm w-icon-sm" />} />
        <MetricTile label="Projects" value={projectCount} detail="Accessible boundaries" icon={<FolderKanban className="h-icon-sm w-icon-sm" />} />
        <MetricTile label="Access grants" value={explicitProjectAccesses} detail="Explicit assignments" icon={<ShieldCheck className="h-icon-sm w-icon-sm" />} />
        <MetricTile label="Role" value={currentRole.toUpperCase()} detail={canManageWorkspace ? 'Workspace management' : 'Read-only view'} icon={<Building2 className="h-icon-sm w-icon-sm" />} />
      </div> : null}

      <div className="max-w-full overflow-x-auto">
        <SegmentedControl
          items={[
            { value: 'overview', label: 'Overview' },
            { value: 'people', label: `People (${peopleCount})` },
            { value: 'access', label: 'Project Access' },
            { value: 'cli-keys', label: 'CLI Keys' },
          ]}
          value={tab}
          onValueChange={(value) => setTab(value as SettingsTab)}
          ariaLabel="Workspace settings"
          size="compact"
        />
      </div>

      {tab === 'overview' ? overview : null}
      {tab === 'people' ? people : null}
      {tab === 'access' ? projectAccess : null}
      {open && tab === 'cli-keys' ? <WorkspaceCliKeys key={workspaceId} workspaceId={workspaceId} projects={projects} onConfigurationChange={setConfiguringCliKey} /> : null}
    </div>
  ) : null

  const inviteView = (
    <div className="grid gap-ui-md">
      <SectionBlock
        title="Invite member"
        description="Configure Workspace role and optional Project access."
      >
        <div className="grid gap-ui-md">
          <Field>
            <FieldLabel>Email</FieldLabel>
            <Input type="email" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} placeholder="person@company.com" />
          </Field>

          <Field>
            <FieldLabel>Workspace role</FieldLabel>
            <div className="grid gap-ui-xs">
              <TechnicalListItem
                label="Member"
                description="Can operate only Projects explicitly assigned to this person."
                selected={inviteRole === 'member'}
                trailing={inviteRole === 'member' ? <Check className="h-icon w-icon text-primary-light" /> : null}
                onClick={() => setInviteRole('member')}
              />
              {canInviteAdmin ? (
                <TechnicalListItem
                  label="Admin"
                  description="Can manage the Workspace and Project access, but still needs explicit access to operate a Project."
                  selected={inviteRole === 'admin'}
                  trailing={inviteRole === 'admin' ? <Check className="h-icon w-icon text-primary-light" /> : null}
                  onClick={() => setInviteRole('admin')}
                />
              ) : null}
            </div>
          </Field>
        </div>
      </SectionBlock>

      <SectionBlock
        title="Project access after acceptance"
        description="Optional. Selected Projects become available immediately when the invitation is accepted."
        density="compact"
      >
        {projects.length ? (
          <div className="scrollbar-thin grid max-h-48 gap-ui-xs overflow-y-auto">
            {projects.map((project) => {
              const checked = inviteProjectIds.includes(project.id)
              return (
                <TechnicalListItem
                  key={project.id}
                  label={project.name}
                  description={`/${project.slug}`}
                  selected={checked}
                  leading={(
                    <Checkbox
                      checked={checked}
                      onClick={(event) => event.stopPropagation()}
                      onChange={() => toggleInviteProject(project.id)}
                      aria-label={`Grant access to ${project.name}`}
                    />
                  )}
                  onClick={() => toggleInviteProject(project.id)}
                />
              )
            })}
          </div>
        ) : (
          <EmptyStatePanel compact title="No Projects available" />
        )}
      </SectionBlock>

      <Alert variant="info">
        <AlertDescription>
          {inviteProjectIds.length ? `${inviteProjectIds.length} Project access grant(s) will be prepared.` : 'The person will join the Workspace without Project access.'}
        </AlertDescription>
      </Alert>

      <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-md">
        <Button variant="outline" onClick={backToMain}>Cancel</Button>
        <Button onClick={handleInvite} loading={createInvite.isPending} disabled={!inviteEmail.trim()}>Send invitation</Button>
      </div>
    </div>
  )

  const removeView = (
    <div className="grid gap-ui-md">
      <SectionBlock
        title="Remove member from Workspace?"
        description={memberToRemove?.email ? `${memberToRemove.email} will lose access to this Workspace.` : undefined}
      >
        <Alert variant="destructive">
          <AlertTitle>Access removal impact</AlertTitle>
          <AlertDescription>
            {memberToRemove?.project_access_count ?? 0} active Project access(es) will be revoked. Pending access grants for this email will be cancelled. Historical traces, releases and audit data remain unchanged.
          </AlertDescription>
        </Alert>
      </SectionBlock>

      <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-md">
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
      className="max-w-dialog-wide"
      scrollMode="content"
    >
      {workspaceQuery.isLoading ? (
        <div className="grid gap-ui-md" aria-label="Loading Workspace">
          <Skeleton className="h-control-row w-full" />
          <div className="grid gap-ui-xs sm:grid-cols-2 xl:grid-cols-4">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
          <Skeleton className="h-48 w-full" />
        </div>
      ) : workspaceQuery.isError ? (
        <Alert variant="destructive">
          <AlertTitle>Unable to load Workspace</AlertTitle>
          <AlertDescription>{workspaceQuery.error instanceof Error ? workspaceQuery.error.message : 'Unknown error'}</AlertDescription>
        </Alert>
      ) : !workspace ? (
        <Alert variant="destructive">
          <AlertTitle>Workspace not found</AlertTitle>
        </Alert>
      ) : view === 'invite' ? inviteView : view === 'remove' ? removeView : mainView}
    </Dialog>
  )
}
