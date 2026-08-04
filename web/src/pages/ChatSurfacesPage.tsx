import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import {
  Copy,
  KeyRound,
  MessageSquare,
  Paintbrush,
  Plus,
  Power,
  RefreshCw,
} from 'lucide-react'
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
import {
  useChatSurfaces,
  useCreateChatSurface,
  useCreateChatSurfaceKey,
  useRefreshChatSurfaceRelease,
  useSetChatSurfaceStatus,
  useUpdateChatSurface,
} from '@/features/chat-surfaces/hooks'
import type {
  ChatSurface,
  ChatSurfaceAccessKey,
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
  const [targetType, setTargetType] =
    useState<ChatSurfaceTargetType>('agent')
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
      appearance: {
        title: displayTitle.trim() || name.trim(),
        theme,
        primary_color: primaryColor,
        placeholder: placeholder.trim(),
        welcome_message: welcomeMessage.trim() || null,
      },
    })
  }

  return (
    <Dialog open onClose={onClose} title="Publish ChatSurface">
      <form
        onSubmit={(event) => void submit(event)}
        className="space-y-5"
      >
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
            Exact HTTPS origin. Wildcards and paths are rejected.
          </span>
        </label>

        <div className="border-t border-border pt-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            Embed appearance
          </p>
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

function AppearanceDialog({
  surface,
  pending,
  onClose,
  onSubmit,
}: {
  surface: ChatSurface
  pending: boolean
  onClose: () => void
  onSubmit: (appearance: ChatSurfaceAppearance) => Promise<void>
}) {
  const current = surface.appearance_config
  const [title, setTitle] = useState(current.title)
  const [theme, setTheme] = useState<ChatSurfaceTheme>(current.theme)
  const [primaryColor, setPrimaryColor] = useState(current.primary_color)
  const [placeholder, setPlaceholder] = useState(current.placeholder)
  const [welcomeMessage, setWelcomeMessage] = useState(current.welcome_message ?? '')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!title.trim() || !placeholder.trim()) {
      toast.error('Display title and placeholder are required')
      return
    }
    await onSubmit({
      title: title.trim(),
      theme,
      primary_color: primaryColor,
      placeholder: placeholder.trim(),
      welcome_message: welcomeMessage.trim() || null,
    })
  }

  return (
    <Dialog open onClose={onClose} title={`Appearance · ${surface.name}`}>
      <form onSubmit={(event) => void submit(event)} className="space-y-4">
        <label className="block" htmlFor="appearance-title">
          <span className="text-xs font-medium text-slate-200">Display title</span>
          <Input
            id="appearance-title"
            autoFocus
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="mt-2"
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block" htmlFor="appearance-theme">
            <span className="text-xs font-medium text-slate-200">Theme</span>
            <select
              id="appearance-theme"
              value={theme}
              onChange={(event) => setTheme(event.target.value as ChatSurfaceTheme)}
              className="mt-2 h-10 w-full rounded-lg border border-border bg-background px-3 text-sm"
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>
          <label className="block" htmlFor="appearance-color">
            <span className="text-xs font-medium text-slate-200">Primary color</span>
            <input
              id="appearance-color"
              type="color"
              value={primaryColor}
              onChange={(event) => setPrimaryColor(event.target.value.toUpperCase())}
              className="mt-2 h-10 w-full rounded-lg border border-border bg-background p-1"
            />
          </label>
        </div>
        <label className="block" htmlFor="appearance-placeholder">
          <span className="text-xs font-medium text-slate-200">Placeholder</span>
          <Input
            id="appearance-placeholder"
            value={placeholder}
            onChange={(event) => setPlaceholder(event.target.value)}
            className="mt-2"
          />
        </label>
        <label className="block" htmlFor="appearance-welcome">
          <span className="text-xs font-medium text-slate-200">Welcome message</span>
          <textarea
            id="appearance-welcome"
            value={welcomeMessage}
            onChange={(event) => setWelcomeMessage(event.target.value)}
            rows={3}
            maxLength={500}
            className="mt-2 w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </label>
        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={pending}>Save appearance</Button>
        </div>
      </form>
    </Dialog>
  )
}

function AccessKeyReveal({
  surface,
  accessKey,
  onClose,
}: {
  surface: ChatSurface
  accessKey: ChatSurfaceAccessKey
  onClose: () => void
}) {
  const value = accessKey.access_key ?? ''
  const backendExample = `WOOBE_CHAT_SURFACE_ID=${surface.public_id}\nWOOBE_CHAT_SURFACE_KEY=${value}`
  return (
    <Dialog open onClose={onClose} title="ChatSurface Access Key">
      <div className="space-y-4">
        <p className="text-sm leading-6 text-muted">
          Store this value in the integrator backend. It will not be shown again
          and must never be included in browser code.
        </p>
        <pre className="max-h-52 overflow-auto rounded-lg border border-border bg-background p-3 text-xs text-slate-200">
          {backendExample}
        </pre>
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              void navigator.clipboard.writeText(backendExample)
              toast.success('Backend configuration copied')
            }}
          >
            <Copy className="mr-2 h-4 w-4" />
            Copy
          </Button>
          <Button type="button" onClick={onClose}>Done</Button>
        </div>
      </div>
    </Dialog>
  )
}

export default function ChatSurfacesPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const surfacesQuery = useChatSurfaces(projectId)
  const agentsQuery = useAgents(projectId)
  const networksQuery = useNetworks(projectId)
  const createMutation = useCreateChatSurface(projectId)
  const updateMutation = useUpdateChatSurface(projectId)
  const releaseMutation = useRefreshChatSurfaceRelease(projectId)
  const statusMutation = useSetChatSurfaceStatus(projectId)
  const keyMutation = useCreateChatSurfaceKey()
  const [creating, setCreating] = useState(false)
  const [editingAppearance, setEditingAppearance] = useState<ChatSurface | null>(null)
  const [revealed, setRevealed] = useState<{
    surface: ChatSurface
    key: ChatSurfaceAccessKey
  } | null>(null)

  const surfaces = surfacesQuery.data ?? []
  const agents = agentsQuery.data ?? []
  const networks = networksQuery.data ?? []
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
              <div key={surface.id} className="relative h-full">
                <ResourceCard
                  icon={<MessageSquare className="h-4 w-4" />}
                  title={surface.name}
                  subtitle={`${surface.target_type} · ${targetName(surface, agents, networks)}`}
                  status={<StatusBadge status={surface.status} size="compact" />}
                  metadata={(
                    <>
                      <span className="rounded-full border border-border px-2 py-1 text-xs text-muted">
                        Production
                      </span>
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
                  footer={(
                    <span className="truncate pr-40 font-mono text-xs">
                      {surface.public_id}
                    </span>
                  )}
                  className="h-full"
                />
                <div className="absolute bottom-2 right-2 flex gap-1">
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    title="Generate Access Key"
                    aria-label={`Generate Access Key for ${surface.name}`}
                    loading={keyMutation.isPending}
                    onClick={async () => {
                      try {
                        const key = await keyMutation.mutateAsync({
                          surfaceId: surface.id,
                        })
                        setRevealed({ surface, key })
                      } catch (error) {
                        toast.error(error instanceof Error ? error.message : 'Unable to generate Access Key')
                      }
                    }}
                  >
                    <KeyRound className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    title="Configure appearance"
                    aria-label={`Configure appearance for ${surface.name}`}
                    onClick={() => setEditingAppearance(surface)}
                  >
                    <Paintbrush className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    title="Use current Production Release for new Sessions"
                    aria-label={`Refresh Production Release for ${surface.name}`}
                    loading={releaseMutation.isPending}
                    disabled={surface.status === 'archived'}
                    onClick={async () => {
                      try {
                        const previousRelease = surface.target_release_id
                        const updated = await releaseMutation.mutateAsync(surface.id)
                        toast.success(
                          updated.target_release_id === previousRelease
                            ? 'ChatSurface already uses the current Production Release'
                            : 'New Sessions will use the current Production Release',
                        )
                      } catch (error) {
                        toast.error(error instanceof Error ? error.message : 'Unable to refresh Release')
                      }
                    }}
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    title={surface.status === 'active' ? 'Disable' : 'Activate'}
                    aria-label={`${surface.status === 'active' ? 'Disable' : 'Activate'} ${surface.name}`}
                    loading={statusMutation.isPending}
                    disabled={surface.status === 'archived'}
                    onClick={async () => {
                      try {
                        await statusMutation.mutateAsync({
                          surfaceId: surface.id,
                          active: surface.status !== 'active',
                        })
                        toast.success(surface.status === 'active' ? 'ChatSurface disabled' : 'ChatSurface activated')
                      } catch (error) {
                        toast.error(error instanceof Error ? error.message : 'Unable to update ChatSurface')
                      }
                    }}
                  >
                    <Power className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
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
              await createMutation.mutateAsync({
                name: input.name,
                target_type: input.targetType,
                target_id: input.targetId,
                allowed_origins: [input.origin],
                appearance_config: input.appearance,
              })
              setCreating(false)
              toast.success('ChatSurface draft created with an immutable Release')
            } catch (error) {
              toast.error(error instanceof Error ? error.message : 'Unable to create ChatSurface')
            }
          }}
        />
      ) : null}

      {editingAppearance ? (
        <AppearanceDialog
          surface={editingAppearance}
          pending={updateMutation.isPending}
          onClose={() => setEditingAppearance(null)}
          onSubmit={async (appearance) => {
            try {
              await updateMutation.mutateAsync({
                surfaceId: editingAppearance.id,
                input: { appearance_config: appearance },
              })
              setEditingAppearance(null)
              toast.success('ChatSurface appearance updated')
            } catch (error) {
              toast.error(error instanceof Error ? error.message : 'Unable to update appearance')
            }
          }}
        />
      ) : null}

      {revealed ? (
        <AccessKeyReveal
          surface={revealed.surface}
          accessKey={revealed.key}
          onClose={() => setRevealed(null)}
        />
      ) : null}
    </ResourcePage>
  )
}
