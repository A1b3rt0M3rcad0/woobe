import { useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, Building2, ChevronRight, MailPlus, Plus, Search, X } from 'lucide-react'
import { Badge, Button, Card, Input, type BadgeVariant } from '@woobe/ui'
import { toast } from 'sonner'

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

function roleVariant(role?: string): BadgeVariant {
  if (role === 'owner') return 'default'
  if (role === 'admin') return 'success'
  return 'outline'
}

function workspaceFooter(workspace: WorkspaceShape) {
  const count = workspace.accessible_project_count ?? 0
  if (workspace.access_mode === 'implicit_owner') return `All Projects · ${count} currently available`
  return `${count} assigned ${count === 1 ? 'Project' : 'Projects'}`
}

function SectionHeading({
  title,
  description,
  count,
}: {
  title: string
  description?: string
  count?: ReactNode
}) {
  return (
    <div className="mb-3">
      <div className="flex items-center gap-2.5">
        <span className="h-[5px] w-[5px] shrink-0 bg-primary" aria-hidden="true" />
        <h2 className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-slate-100">{title}</h2>
        <span className="h-px min-w-6 flex-1 bg-border" />
        {count !== undefined && (
          <span className="shrink-0 font-mono text-[9px] text-muted-foreground">{count}</span>
        )}
      </div>
      {description && (
        <p className="mt-1.5 pl-[15px] font-mono text-[9px] leading-4 text-muted-foreground">{description}</p>
      )}
    </div>
  )
}

function WorkspaceSearch({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="relative w-full max-w-sm">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
      <Input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && value) {
            event.preventDefault()
            onChange('')
          }
        }}
        placeholder="Search Workspaces..."
        aria-label="Search Workspaces"
        className="pl-9 pr-9 font-mono text-[10px]"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear search"
          className="absolute right-1 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-technical text-muted-foreground transition-colors hover:bg-accent hover:text-slate-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}

function WorkspaceCard({ workspace, onSelect }: { workspace: WorkspaceShape; onSelect: () => void }) {
  const accessLabel = workspace.access_mode === 'implicit_owner'
    ? 'Implicit all-Project access'
    : 'Explicit Project access'

  return (
    <button
      type="button"
      aria-label={`Open Projects for ${workspace.name}`}
      onClick={onSelect}
      className="group flex min-h-[136px] w-full flex-col rounded-container border border-border bg-surface text-left transition-colors hover:border-slate-600 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
    >
      <span className="flex flex-1 items-start justify-between gap-4 p-4">
        <span className="flex min-w-0 items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-border bg-control font-mono text-[10px] font-bold text-primary-light">
            {getInitials(workspace.name)}
          </span>
          <span className="min-w-0">
            <span className="block truncate font-mono text-xs font-bold tracking-[0.01em] text-slate-50">{workspace.name}</span>
            <span className="mt-1 block truncate font-mono text-[9px] text-muted-foreground">/{workspace.slug}</span>
            <span className="mt-3 block font-mono text-[8px] uppercase tracking-[0.08em] text-muted">
              {accessLabel}
            </span>
          </span>
        </span>
        <Badge
          variant={roleVariant(workspace.membership_role)}
          className="shrink-0 font-mono text-[8px] uppercase tracking-[0.08em]"
        >
          {workspace.membership_role ?? 'member'}
        </Badge>
      </span>
      <span className="flex w-full items-center justify-between gap-3 border-t border-border bg-control/35 px-4 py-2.5">
        <span className="truncate font-mono text-[9px] text-muted-foreground">{workspaceFooter(workspace)}</span>
        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary-light" />
      </span>
    </button>
  )
}

function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: ReactNode
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <Card className="border-dashed px-6 py-10 text-center">
      <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-control border border-border bg-control text-muted-foreground">
        {icon}
      </div>
      <h3 className="mt-3 font-mono text-[11px] font-bold text-slate-100">{title}</h3>
      <p className="mx-auto mt-1.5 max-w-lg font-mono text-[9px] leading-4 text-muted-foreground">{description}</p>
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </Card>
  )
}

function WorkspaceLoadingGrid({ count = 3 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: count }).map((_, index) => (
        <Card key={index} className="min-h-[136px] animate-pulse p-4">
          <div className="flex items-start gap-3">
            <div className="h-8 w-8 rounded-control bg-accent" />
            <div className="flex-1 space-y-2">
              <div className="h-2.5 w-2/3 bg-accent" />
              <div className="h-2 w-1/2 bg-accent/80" />
              <div className="mt-4 h-2 w-1/3 bg-accent/70" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
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
  const workspaceErrorMessage = workspaceError instanceof Error ? workspaceError.message : 'Failed to load Workspaces'

  return (
    <div className="mx-auto w-full max-w-[1540px]">
      <header className="flex flex-col gap-4 border-b border-border pb-4 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-7 w-8 shrink-0 items-center border-r border-border text-primary-light">
            <Building2 className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h1 className="font-mono text-base font-bold tracking-[0.01em] text-slate-50">Workspaces</h1>
            <p className="mt-0.5 truncate font-mono text-[9px] text-muted-foreground">
              Select the commercial workspace you want to operate.
            </p>
          </div>
        </div>
        <Button type="button" onClick={() => setShowCreate(true)}>
          <Plus className="h-3.5 w-3.5" />
          Create Workspace
        </Button>
      </header>

      <div className="space-y-6 pt-5">
        {(isLoadingInvites || pendingInvites.length > 0) && (
          <section>
            <SectionHeading
              title="Invitations"
              description="Accept an invitation to join a Workspace. Prepared Project access is applied immediately after acceptance."
              count={pendingInvites.length}
            />
            {isLoadingInvites ? (
              <WorkspaceLoadingGrid count={2} />
            ) : (
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                {pendingInvites.map((invite) => (
                  <Card key={invite.id} className="flex items-center justify-between gap-4 p-4">
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">
                        <MailPlus className="h-3.5 w-3.5" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate font-mono text-[11px] font-bold text-slate-100">{invite.workspace_name}</p>
                        <p className="mt-1 truncate font-mono text-[9px] text-muted-foreground">
                          /{invite.workspace_slug} · {invite.role} · {invite.project_count ?? 0} prepared Project(s)
                        </p>
                      </div>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      loading={acceptingInviteId === invite.id}
                      disabled={acceptingInviteId !== null && acceptingInviteId !== invite.id}
                      onClick={() => handleAcceptInvite(invite.id)}
                    >
                      Accept and enter
                    </Button>
                  </Card>
                ))}
              </div>
            )}
          </section>
        )}

        <section>
          <SectionHeading
            title="Workspaces"
            description="Workspaces own Projects, members, plans and usage."
            count={resultCount}
          />

          {showSearch && (
            <div className="mb-3 flex justify-end">
              <WorkspaceSearch value={query} onChange={setQuery} />
            </div>
          )}

          {isLoadingWorkspaces ? (
            <WorkspaceLoadingGrid />
          ) : workspaceError ? (
            <Card className="border-error/30 bg-error/[0.05] px-6 py-10 text-center">
              <AlertCircle className="mx-auto h-5 w-5 text-red-300" />
              <h3 className="mt-3 font-mono text-[11px] font-bold text-slate-100">Unable to load Workspaces</h3>
              <p className="mx-auto mt-1.5 max-w-lg font-mono text-[9px] leading-4 text-red-200/80">{workspaceErrorMessage}</p>
            </Card>
          ) : workspaces.length === 0 ? (
            <EmptyState
              icon={<Building2 className="h-3.5 w-3.5" />}
              title="Create your first Workspace"
              description={pendingInvites.length > 0
                ? 'Accept an invitation above or create a new Workspace.'
                : 'Workspaces are the commercial workspace for Projects, members, plans and usage.'}
              action={<Button type="button" size="sm" onClick={() => setShowCreate(true)}>Create Workspace</Button>}
            />
          ) : hasSearchMiss ? (
            <EmptyState
              icon={<Search className="h-3.5 w-3.5" />}
              title="No Workspaces found"
              description="Adjust your search or clear the current term."
              action={<Button type="button" size="sm" variant="outline" onClick={() => setQuery('')}>Clear search</Button>}
            />
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {visibleWorkspaces.map((workspace) => (
                <WorkspaceCard key={workspace.id} workspace={workspace} onSelect={() => handleSelect(workspace)} />
              ))}
            </div>
          )}
        </section>
      </div>

      <CreateWorkspaceDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={handleCreate}
        loading={createWorkspace.isPending}
      />
    </div>
  )
}
