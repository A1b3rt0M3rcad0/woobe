import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Boxes, MailPlus, Plus } from 'lucide-react'
import { toast } from 'sonner'

import { ResourceCard, ResourcePill } from '@/components/common/OperationalResourceCard'
import { ResourceEmptyState, ResourcePage, ResourceSearch, ResourceSectionHeader, ResourceToolbar } from '@/components/common/ResourcePage'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { acceptWorkspaceInvite, createWorkspace, getPendingWorkspaceInvites } from '@/features/workspaces/api'
import { slugify } from '@/lib/slug'

const SEARCH_THRESHOLD = 5

export default function WorkspacesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { workspaces, selectWorkspace, isLoadingWorkspaces, workspaceError } = useWorkspace()
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [query, setQuery] = useState('')

  const pendingQuery = useQuery({ queryKey: ['workspace-invites', 'pending-for-user'], queryFn: getPendingWorkspaceInvites })
  const createMutation = useMutation({
    mutationFn: () => createWorkspace({ name: name.trim(), slug: slugify(name, 'workspace') }),
    onSuccess: (workspace) => {
      void queryClient.invalidateQueries({ queryKey: ['workspaces'] })
      selectWorkspace(workspace)
      setShowCreate(false)
      setName('')
      navigate(`/workspaces/${workspace.id}/projects`)
    },
  })
  const acceptMutation = useMutation({
    mutationFn: acceptWorkspaceInvite,
    onSuccess: (workspace) => {
      void queryClient.invalidateQueries({ queryKey: ['workspaces'] })
      void queryClient.invalidateQueries({ queryKey: ['workspace-invites'] })
      selectWorkspace(workspace)
      navigate(`/workspaces/${workspace.id}/projects`)
    },
  })

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return workspaces
    return workspaces.filter((workspace) => `${workspace.name} ${workspace.slug}`.toLowerCase().includes(term))
  }, [query, workspaces])

  const openWorkspace = (workspace: (typeof workspaces)[number]) => {
    selectWorkspace(workspace)
    navigate(`/workspaces/${workspace.id}/projects`)
  }

  return (
    <ResourcePage
      title="Workspaces"
      description="Organize Projects and members inside this Woobe Instance."
      action={<Button onClick={() => setShowCreate(true)}><Plus className="mr-2 h-4 w-4" />Create Workspace</Button>}
    >
      {(pendingQuery.isLoading || (pendingQuery.data?.length ?? 0) > 0) && (
        <section>
          <ResourceSectionHeader title="Invitations" description="Join the Workspace assigned to your user." count={pendingQuery.data?.length ?? 0} />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {(pendingQuery.data ?? []).map((invite) => (
              <ResourceCard
                key={invite.id}
                icon={<MailPlus className="h-4 w-4" />}
                title={invite.workspace_name}
                subtitle={`/${invite.workspace_slug}`}
                footer={`${invite.project_count ?? 0} prepared Project(s)`}
                status={<Button size="sm" loading={acceptMutation.isPending} onClick={(event) => { event.stopPropagation(); void acceptMutation.mutateAsync(invite.id).catch((error) => toast.error(error instanceof Error ? error.message : 'Failed to accept invite')) }}>Accept</Button>}
              />
            ))}
          </div>
        </section>
      )}

      {workspaces.length >= SEARCH_THRESHOLD && (
        <ResourceToolbar><ResourceSearch value={query} onChange={setQuery} placeholder="Search Workspaces..." label="Search Workspaces" /></ResourceToolbar>
      )}

      <section>
        <ResourceSectionHeader title="Workspaces" description="The Instance admin owns all Workspaces; members belong to one Workspace." count={visible.length} />
        {isLoadingWorkspaces ? null : workspaceError ? (
          <ResourceEmptyState icon={<Boxes className="h-4 w-4" />} title="Unable to load Workspaces" description={workspaceError.message} />
        ) : visible.length === 0 ? (
          <ResourceEmptyState icon={<Boxes className="h-4 w-4" />} title="No Workspaces" description="Create the first operational Workspace for this Instance." action={<Button size="sm" onClick={() => setShowCreate(true)}>Create Workspace</Button>} />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visible.map((workspace) => (
              <ResourceCard
                key={workspace.id}
                onClick={() => openWorkspace(workspace)}
                icon={<Boxes className="h-4 w-4" />}
                title={workspace.name}
                subtitle={`/${workspace.slug}`}
                status={<ResourcePill tone={workspace.can_manage ? 'primary' : 'default'}>{workspace.can_manage ? 'ADMIN' : 'MEMBER'}</ResourcePill>}
                footer="Open Projects"
              />
            ))}
          </div>
        )}
      </section>

      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="Create Workspace">
        <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (!name.trim()) return; void createMutation.mutateAsync().then(() => toast.success('Workspace created')).catch((error) => toast.error(error instanceof Error ? error.message : 'Failed to create Workspace')) }}>
          <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Workspace name" />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button type="submit" loading={createMutation.isPending}>Create</Button>
          </div>
        </form>
      </Dialog>
    </ResourcePage>
  )
}
