import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, MailPlus, Plus } from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard, ResourcePill } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { CreateWorkspaceDialog } from '@/components/forms/CreateWorkspaceDialog'
import {
  useAcceptWorkspaceInvite,
  useCreateWorkspace,
  usePendingWorkspaceInvites,
} from '@/features/workspaces/hooks'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import type { WorkspaceShape } from '@/features/workspace/types'

const SEARCH_THRESHOLD = 5

function getInitials(name: string) {
  return name.split(' ').filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'OR'
}

function roleTone(role?: string): 'primary' | 'success' | 'default' {
  return role === 'owner' ? 'primary' : role === 'admin' ? 'success' : 'default'
}

function workspaceFooter(workspace: WorkspaceShape) {
  const count = workspace.accessible_project_count ?? 0
  if (workspace.access_mode === 'implicit_owner') return `All Projects · ${count} currently available`
  return `${count} assigned ${count === 1 ? 'Project' : 'Projects'}`
}

export default function WorkspacesPage() {
  const { workspaces, selectWorkspace, isLoadingWorkspaces, workspaceError } = useWorkspace()
  const createWorkspace = useCreateWorkspace()
  const { data: pendingInvites = [], isLoading: isLoadingInvites } = usePendingWorkspaceInvites()
  const acceptInvite = useAcceptWorkspaceInvite()
  const navigate = useNavigate()
  const [showCreate, setShowCreate] = useState(false)
  const [query, setQuery] = useState('')
  const [acceptingInviteId, setAcceptingInviteId] = useState<string | null>(null)

  const visibleWorkspaces = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return workspaces
    return workspaces.filter((workspace) => `${workspace.name} ${workspace.slug} ${workspace.membership_role ?? ''}`.toLowerCase().includes(normalizedQuery))
  }, [workspaces, query])

  const handleCreate = async (data: { name: string; slug: string }) => {
    try {
      const workspace = await createWorkspace.mutateAsync(data)
      toast.success('Workspace created')
      setShowCreate(false)
      selectWorkspace({
        id: workspace.id,
        name: workspace.name,
        slug: workspace.slug,
        membership_role: 'owner',
        can_manage_workspace: true,
        accessible_project_count: 0,
        access_mode: 'implicit_owner',
      })
      navigate(`/workspaces/${workspace.id}/projects`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create workspace')
    }
  }

  const handleAcceptInvite = async (inviteId: string) => {
    setAcceptingInviteId(inviteId)
    try {
      const pendingInvite = pendingInvites.find((invite) => invite.id === inviteId)
      const workspace = await acceptInvite.mutateAsync(inviteId)
      const membershipRole = pendingInvite?.role === 'admin' ? 'admin' : 'member'
      selectWorkspace({
        id: workspace.id,
        name: workspace.name,
        slug: workspace.slug,
        membership_role: membershipRole,
        can_manage_workspace: membershipRole === 'admin',
        accessible_project_count: pendingInvite?.project_count ?? 0,
        access_mode: 'assigned_projects',
      })
      toast.success(`Joined ${workspace.name}`)
      navigate(`/workspaces/${workspace.id}/projects`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to accept invitation')
    } finally {
      setAcceptingInviteId(null)
    }
  }

  const handleSelect = (workspace: WorkspaceShape) => {
    selectWorkspace(workspace)
    navigate(`/workspaces/${workspace.id}/projects`)
  }

  const showSearch = workspaces.length >= SEARCH_THRESHOLD
  const hasSearchMiss = Boolean(query.trim()) && visibleWorkspaces.length === 0
  const resultCount = query.trim() ? `${visibleWorkspaces.length} of ${workspaces.length}` : workspaces.length

  return (
    <ResourcePage
      title="Workspaces"
      description="Select the commercial workspace you want to operate."
      action={<Button type="button" onClick={() => setShowCreate(true)}><Plus className="mr-2 h-4 w-4" />Create Workspace</Button>}
    >
      {(isLoadingInvites || pendingInvites.length > 0) && (
        <section>
          <ResourceSectionHeader
            title="Invitations"
            description="Accept an invitation to join a Workspace. Prepared Project access is applied immediately after acceptance."
            count={pendingInvites.length}
          />
          {isLoadingInvites ? (
            <LoadingState message="Loading invitations" variant="panel" layout="compact-cards" />
          ) : (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {pendingInvites.map((invite) => (
                <Card key={invite.id}>
                  <CardContent className="flex items-center justify-between gap-4 p-4">
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10"><MailPlus className="h-4 w-4 text-primary-light" /></div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-white">{invite.workspace_name}</p>
                        <p className="truncate text-xs text-muted">/{invite.workspace_slug} · {invite.role} · {invite.project_count ?? 0} prepared Project(s)</p>
                      </div>
                    </div>
                    <Button type="button" size="sm" loading={acceptingInviteId === invite.id} disabled={acceptingInviteId !== null && acceptingInviteId !== invite.id} onClick={() => handleAcceptInvite(invite.id)}>Accept and enter</Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </section>
      )}

      {showSearch && <ResourceToolbar><ResourceSearch value={query} onChange={setQuery} placeholder="Search Workspaces..." label="Search Workspaces" /></ResourceToolbar>}

      <section>
        <ResourceSectionHeader title="Workspaces" description="Workspaces own Projects, members, plans and usage." count={resultCount} />
        {isLoadingWorkspaces ? (
          <LoadingState message="Loading Workspaces" variant="panel" layout="compact-cards" />
        ) : workspaceError ? (
          <ErrorState error={workspaceError} className="rounded-xl border border-border/80 bg-surface/40 py-10" />
        ) : workspaces.length === 0 ? (
          <ResourceEmptyState icon={<Building2 className="h-4 w-4" />} title="Create your first Workspace" description={pendingInvites.length > 0 ? 'Accept an invitation above or create a new Workspace.' : 'Workspaces are the commercial workspace for Projects, members, plans and usage.'} action={<Button type="button" size="sm" onClick={() => setShowCreate(true)}>Create Workspace</Button>} />
        ) : hasSearchMiss ? (
          <ResourceEmptyState icon={<Building2 className="h-4 w-4" />} title="No Workspaces found" description="Adjust your search or clear the current term." action={<Button type="button" size="sm" variant="outline" onClick={() => setQuery('')}>Clear search</Button>} />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visibleWorkspaces.map((workspace) => (
              <ResourceCard
                key={workspace.id}
                aria-label={`Open Projects for ${workspace.name}`}
                onClick={() => handleSelect(workspace)}
                icon={<span className="text-xs font-semibold">{getInitials(workspace.name)}</span>}
                title={workspace.name}
                subtitle={`/${workspace.slug}`}
                status={<ResourcePill tone={roleTone(workspace.membership_role)}>{(workspace.membership_role ?? 'member').toUpperCase()}</ResourcePill>}
                metadata={<ResourcePill>{workspace.access_mode === 'implicit_owner' ? 'Implicit all-Project access' : 'Explicit Project access'}</ResourcePill>}
                footer={workspaceFooter(workspace)}
              />
            ))}
          </div>
        )}
      </section>

      <CreateWorkspaceDialog open={showCreate} onClose={() => setShowCreate(false)} onSubmit={handleCreate} loading={createWorkspace.isPending} />
    </ResourcePage>
  )
}
