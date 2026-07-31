import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Copy, KeyRound, MessageSquare, Plus, Power } from 'lucide-react'
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
  useSetChatSurfaceStatus,
} from '@/features/chat-surfaces/hooks'
import type {
  ChatSurface,
  ChatSurfaceAccessKey,
  ChatSurfaceTargetType,
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
  }) => Promise<void>
}) {
  const [name, setName] = useState('')
  const [targetType, setTargetType] =
    useState<ChatSurfaceTargetType>('agent')
  const [targetId, setTargetId] = useState('')
  const [origin, setOrigin] = useState('')
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

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={pending}>Create draft</Button>
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
  const statusMutation = useSetChatSurfaceStatus(projectId)
  const keyMutation = useCreateChatSurfaceKey()
  const [creating, setCreating] = useState(false)
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
      description="Publish Production Agents and Networks as secure embedded conversations."
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
                      <span className="rounded-full border border-border px-2 py-1 text-xs text-muted">
                        {surface.allowed_origins.length} {surface.allowed_origins.length === 1 ? 'origin' : 'origins'}
                      </span>
                    </>
                  )}
                  footer={(
                    <span className="truncate pr-24 font-mono text-xs">
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
              })
              setCreating(false)
              toast.success('ChatSurface draft created')
            } catch (error) {
              toast.error(error instanceof Error ? error.message : 'Unable to create ChatSurface')
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
