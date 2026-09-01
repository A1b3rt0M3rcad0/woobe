import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { MessageSquare, Plus } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSectionHeader,
} from '@/components/common/ResourcePage'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { useAgents } from '@/features/agents/hooks'
import { createDefaultChatSurfaceAppearance } from '@/features/chat-surfaces/appearance'
import { ChatSurfaceDetailsModal } from '@/features/chat-surfaces/components/ChatSurfaceDetailsModal'
import {
  useChatSurfaces,
  useCreateChatSurface,
} from '@/features/chat-surfaces/hooks'
import type {
  ChatSurface,
  ChatSurfaceAppearance,
  ChatSurfaceTargetType,
  ChatSurfaceTheme,
} from '@/features/chat-surfaces/types'
import { useNetworks } from '@/features/network/hooks'

function targetName(
  surface: ChatSurface,
  agents: Array<{ id: string; name: string }>,
  networks: Array<{ id: string; name: string }>,
) {
  const candidates = surface.target_type === 'agent' ? agents : networks
  return candidates.find((item) => item.id === surface.target_id)?.name
    ?? surface.target_id
}

function CreateSurfaceDialog({
  pending,
  agents,
  networks,
  onClose,
  onSubmit,
}: {
  pending: boolean
  agents: Array<{ id: string; name: string }>
  networks: Array<{ id: string; name: string }>
  onClose: () => void
  onSubmit: (input: {
    name: string
    targetType: ChatSurfaceTargetType
    targetId: string
    origin: string
    appearance: ChatSurfaceAppearance
  }) => Promise<void>
}) {
  const [name, setName] = useState('')
  const [targetType, setTargetType] = useState<ChatSurfaceTargetType>('agent')
  const [targetId, setTargetId] = useState('')
  const [origin, setOrigin] = useState('')
  const [displayTitle, setDisplayTitle] = useState('')
  const [theme, setTheme] = useState<ChatSurfaceTheme>('system')
  const [primaryColor, setPrimaryColor] = useState('#5B47E0')
  const [placeholder, setPlaceholder] = useState('Type a message…')
  const [welcomeMessage, setWelcomeMessage] = useState('')
  const targets = targetType === 'agent' ? agents : networks

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim() || !targetId || !origin.trim()) {
      toast.error('Name, Production target and allowed origin are required')
      return
    }

    await onSubmit({
      name: name.trim(),
      targetType,
      targetId,
      origin: origin.trim(),
      appearance: createDefaultChatSurfaceAppearance({
        title: displayTitle.trim() || name.trim(),
        theme,
        primary_color: primaryColor,
        placeholder: placeholder.trim(),
        welcome_message: welcomeMessage.trim() || null,
      }),
    })
  }

  return (
    <Dialog open onClose={onClose} title="Publish ChatSurface">
      <form onSubmit={(event) => void submit(event)} className="space-y-5">
        <label className="block" htmlFor="surface-name">
          <span className="text-xs font-medium text-slate-200">Name</span>
          <Input
            id="surface-name"
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Product support chat"
            className="mt-2"
          />
        </label>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block" htmlFor="surface-target-type">
            <span className="text-xs font-medium text-slate-200">Target type</span>
            <select
              id="surface-target-type"
              value={targetType}
              onChange={(event) => {
                setTargetType(event.target.value as ChatSurfaceTargetType)
                setTargetId('')
              }}
              className="mt-2 h-10 w-full rounded-lg border border-border bg-background px-3 text-sm"
            >
              <option value="agent">Agent</option>
              <option value="network">Network</option>
            </select>
          </label>
          <label className="block" htmlFor="surface-target">
            <span className="text-xs font-medium text-slate-200">Production target</span>
            <select
              id="surface-target"
              value={targetId}
              onChange={(event) => setTargetId(event.target.value)}
              className="mt-2 h-10 w-full rounded-lg border border-border bg-background px-3 text-sm"
            >
              <option value="">Select target</option>
              {targets.map((target) => (
                <option key={target.id} value={target.id}>{target.name}</option>
              ))}
            </select>
          </label>
        </div>

        <label className="block" htmlFor="surface-origin">
          <span className="text-xs font-medium text-slate-200">Allowed origin</span>
          <Input
            id="surface-origin"
            value={origin}
            onChange={(event) => setOrigin(event.target.value)}
            placeholder="https://app.example.com"
            className="mt-2"
          />
          <span className="mt-1 block text-xs text-muted">
            Exact HTTPS origin. Local HTTP is accepted only when enabled by the deployment.
          </span>
        </label>

        <div className="border-t border-border pt-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Embed appearance</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="block" htmlFor="surface-display-title">
              <span className="text-xs font-medium text-slate-200">Display title</span>
              <Input
                id="surface-display-title"
                value={displayTitle}
                onChange={(event) => setDisplayTitle(event.target.value)}
                placeholder={name.trim() || 'Woobe'}
                className="mt-2"
              />
            </label>
            <label className="block" htmlFor="surface-theme">
              <span className="text-xs font-medium text-slate-200">Theme</span>
              <select
                id="surface-theme"
                value={theme}
                onChange={(event) => setTheme(event.target.value as ChatSurfaceTheme)}
                className="mt-2 h-10 w-full rounded-lg border border-border bg-background px-3 text-sm"
              >
                <option value="system">System</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </label>
            <label className="block" htmlFor="surface-color">
              <span className="text-xs font-medium text-slate-200">Primary color</span>
              <input
                id="surface-color"
                type="color"
                value={primaryColor}
                onChange={(event) => setPrimaryColor(event.target.value.toUpperCase())}
                className="mt-2 h-10 w-full rounded-lg border border-border bg-background p-1"
              />
            </label>
            <label className="block" htmlFor="surface-placeholder">
              <span className="text-xs font-medium text-slate-200">Placeholder</span>
              <Input
                id="surface-placeholder"
                value={placeholder}
                onChange={(event) => setPlaceholder(event.target.value)}
                className="mt-2"
              />
            </label>
          </div>
          <label className="mt-4 block" htmlFor="surface-welcome">
            <span className="text-xs font-medium text-slate-200">Welcome message</span>
            <textarea
              id="surface-welcome"
              value={welcomeMessage}
              onChange={(event) => setWelcomeMessage(event.target.value)}
              rows={3}
              maxLength={500}
              placeholder="How can I help?"
              className="mt-2 w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
          </label>
        </div>

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={pending}>Create draft</Button>
        </div>
      </form>
    </Dialog>
  )
}

export default function ChatSurfacesPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const surfacesQuery = useChatSurfaces(projectId)
  const agentsQuery = useAgents(projectId)
  const networksQuery = useNetworks(projectId)
  const createMutation = useCreateChatSurface(projectId)
  const [creating, setCreating] = useState(false)
  const [selectedSurfaceId, setSelectedSurfaceId] = useState<string | null>(null)

  const surfaces = surfacesQuery.data ?? []
  const agents = agentsQuery.data ?? []
  const networks = networksQuery.data ?? []
  const selectedSurface = selectedSurfaceId
    ? surfaces.find((surface) => surface.id === selectedSurfaceId) ?? null
    : null
  const selectedTargetName = selectedSurface
    ? targetName(selectedSurface, agents, networks)
    : ''
  const activeCount = useMemo(
    () => surfaces.filter((surface) => surface.status === 'active').length,
    [surfaces],
  )

  if (!projectId) return <ErrorState message="Project not found" />

  return (
    <ResourcePage
      title="ChatSurfaces"
      description="Publish immutable Production Agents and Networks as secure embedded conversations."
      action={(
        <Button type="button" onClick={() => setCreating(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Publish ChatSurface
        </Button>
      )}
    >
      <section>
        <ResourceSectionHeader
          title="Surfaces"
          description={`${activeCount} active · ${surfaces.length} total`}
          count={surfaces.length}
        />

        {surfacesQuery.isLoading ? (
          <LoadingState message="Loading ChatSurfaces" variant="panel" layout="compact-cards" />
        ) : surfacesQuery.isError ? (
          <ErrorState
            error={surfacesQuery.error}
            onRetry={surfacesQuery.refetch}
            className="rounded-xl border border-border/80 bg-surface/40 py-10"
          />
        ) : surfaces.length === 0 ? (
          <ResourceEmptyState
            icon={<MessageSquare className="h-4 w-4" />}
            title="Publish your first ChatSurface"
            description="Choose a Production Agent or Network, authorize an exact origin and generate a backend-only Access Key."
            action={(
              <Button type="button" size="sm" onClick={() => setCreating(true)}>
                Publish ChatSurface
              </Button>
            )}
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {surfaces.map((surface) => (
              <ResourceCard
                key={surface.id}
                aria-label={`Open ChatSurface ${surface.name}`}
                onClick={() => setSelectedSurfaceId(surface.id)}
                icon={<MessageSquare className="h-4 w-4" />}
                title={surface.name}
                subtitle={`${surface.target_type === 'agent' ? 'Agent' : 'Network'} · ${targetName(surface, agents, networks)}`}
                status={<StatusBadge status={surface.status} size="compact" />}
                metadata={(
                  <>
                    <span className="rounded-full border border-border px-2 py-1 text-xs text-muted">Production</span>
                    <span
                      className="rounded-full border border-border px-2 py-1 font-mono text-xs text-muted"
                      title={surface.target_release_id}
                    >
                      Release {surface.target_release_id.slice(0, 8)}
                    </span>
                    <span className="rounded-full border border-border px-2 py-1 text-xs text-muted">
                      {surface.allowed_origins.length} {surface.allowed_origins.length === 1 ? 'origin' : 'origins'}
                    </span>
                  </>
                )}
                footer={<span className="truncate font-mono text-xs">{surface.public_id}</span>}
                className="h-full"
              />
            ))}
          </div>
        )}
      </section>

      {creating ? (
        <CreateSurfaceDialog
          pending={createMutation.isPending}
          agents={agents}
          networks={networks}
          onClose={() => setCreating(false)}
          onSubmit={async (input) => {
            try {
              const created = await createMutation.mutateAsync({
                name: input.name,
                target_type: input.targetType,
                target_id: input.targetId,
                allowed_origins: [input.origin],
                appearance_config: input.appearance,
              })
              setCreating(false)
              setSelectedSurfaceId(created.id)
              toast.success('ChatSurface draft created with an immutable Release')
            } catch (error) {
              toast.error(error instanceof Error ? error.message : 'Unable to create ChatSurface')
            }
          }}
        />
      ) : null}

      <ChatSurfaceDetailsModal
        open={Boolean(selectedSurfaceId)}
        surfaceId={selectedSurfaceId}
        projectId={projectId}
        targetName={selectedTargetName}
        onClose={() => setSelectedSurfaceId(null)}
      />
    </ResourcePage>
  )
}
