import { useMemo, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Bot, Check, MessageSquare, Network, Plus } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Button, Input, Select, Textarea } from '@woobe/ui'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard, ResourcePill } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSectionHeader,
} from '@/components/common/ResourcePage'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Dialog } from '@/components/ui/Dialog'
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

function FormSectionHeader({ title, description }: { title: string; description: string }) {
  return (
    <div>
      <h3 className="font-mono text-[10px] font-bold text-slate-50">{title}</h3>
      <p className="mt-1 font-sans text-[10px] leading-4 text-muted-foreground">{description}</p>
    </div>
  )
}

function FormField({ label, description, children }: { label: string; description?: string; children: ReactNode }) {
  return (
    <label className="grid min-w-0 gap-1.5">
      <span className="font-mono text-[8px] font-medium uppercase tracking-[0.1em] text-muted-foreground">{label}</span>
      {children}
      {description ? <span className="font-sans text-[9px] leading-4 text-muted-foreground">{description}</span> : null}
    </label>
  )
}

function TargetTypeChoice({
  type,
  active,
  title,
  description,
  icon,
  onClick,
}: {
  type: ChatSurfaceTargetType
  active: boolean
  title: string
  description: string
  icon: ReactNode
  onClick: (type: ChatSurfaceTargetType) => void
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={() => onClick(type)}
      className={`flex min-h-[48px] items-center gap-2.5 rounded-control border px-3 text-left transition-colors ${
        active
          ? 'border-primary/45 bg-primary/[0.10] text-slate-50'
          : 'border-border bg-control/25 text-muted-foreground hover:border-slate-600 hover:bg-control/45 hover:text-slate-200'
      }`}
    >
      <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-control border ${active ? 'border-primary/35 bg-primary/[0.08] text-primary-light' : 'border-border bg-control text-muted-foreground'}`}>
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-mono text-[9px] font-semibold">{title}</span>
        <span className="mt-0.5 block font-sans text-[9px] leading-4 text-muted-foreground">{description}</span>
      </span>
      <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${active ? 'border-primary bg-primary text-white' : 'border-border bg-background'}`}>
        {active ? <Check className="h-2.5 w-2.5" /> : null}
      </span>
    </button>
  )
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
  const [primaryColor, setPrimaryColor] = useState('#3B82F6')
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
    <Dialog open onClose={onClose} title="Create ChatSurface" className="max-w-[900px]">
      <form onSubmit={(event) => void submit(event)}>
        <section className="border-b border-border pb-4">
          <FormSectionHeader title="Surface identity" description="Name the embedded conversation and bind it to one immutable Production target." />
          <div className="mt-3 grid gap-4 lg:grid-cols-2">
            <FormField label="Name">
              <Input
                id="surface-name"
                autoFocus
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Product support chat"
              />
            </FormField>
            <FormField label="Production target">
              <Select
                id="surface-target"
                value={targetId}
                onChange={(event) => setTargetId(event.target.value)}
                placeholder="Select target"
                options={targets.map((target) => ({ value: target.id, label: target.name }))}
              />
            </FormField>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <TargetTypeChoice
              type="agent"
              active={targetType === 'agent'}
              title="Agent"
              description="Expose one Production Agent through the Surface."
              icon={<Bot className="h-3.5 w-3.5" />}
              onClick={(next) => { setTargetType(next); setTargetId('') }}
            />
            <TargetTypeChoice
              type="network"
              active={targetType === 'network'}
              title="Network"
              description="Expose one Production Network through the Surface."
              icon={<Network className="h-3.5 w-3.5" />}
              onClick={(next) => { setTargetType(next); setTargetId('') }}
            />
          </div>
        </section>

        <section className="border-b border-border py-4">
          <FormSectionHeader title="Origin access" description="Authorize the exact browser origin allowed to request ChatSurface Sessions." />
          <div className="mt-3">
            <FormField label="Allowed origin" description="Exact HTTPS origin. Local HTTP is accepted only when enabled by the deployment.">
              <Input
                id="surface-origin"
                value={origin}
                onChange={(event) => setOrigin(event.target.value)}
                placeholder="https://app.example.com"
              />
            </FormField>
          </div>
        </section>

        <section className="py-4">
          <FormSectionHeader title="Embed appearance" description="Initial visual identity. Fine-grained appearance remains editable after creation." />
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <FormField label="Display title">
              <Input
                id="surface-display-title"
                value={displayTitle}
                onChange={(event) => setDisplayTitle(event.target.value)}
                placeholder={name.trim() || 'Woobe'}
              />
            </FormField>
            <FormField label="Theme">
              <Select
                id="surface-theme"
                value={theme}
                onChange={(event) => setTheme(event.target.value as ChatSurfaceTheme)}
                options={[
                  { value: 'system', label: 'System' },
                  { value: 'light', label: 'Light' },
                  { value: 'dark', label: 'Dark' },
                ]}
              />
            </FormField>
            <FormField label="Primary color">
              <div className="flex h-[34px] items-center gap-2 rounded-control border border-border bg-control px-2.5">
                <input
                  id="surface-color"
                  type="color"
                  value={primaryColor}
                  onChange={(event) => setPrimaryColor(event.target.value.toUpperCase())}
                  className="h-6 w-7 shrink-0 rounded-technical border border-border bg-control p-0.5"
                />
                <code className="font-mono text-[9px] text-muted-foreground">{primaryColor}</code>
              </div>
            </FormField>
            <FormField label="Placeholder">
              <Input
                id="surface-placeholder"
                value={placeholder}
                onChange={(event) => setPlaceholder(event.target.value)}
              />
            </FormField>
          </div>
          <div className="mt-4">
            <FormField label="Welcome message" description="Optional initial assistant message shown before the first user message.">
              <Textarea
                id="surface-welcome"
                value={welcomeMessage}
                onChange={(event) => setWelcomeMessage(event.target.value)}
                rows={3}
                maxLength={500}
                placeholder="How can I help?"
              />
            </FormField>
          </div>
        </section>

        <div className="flex items-center justify-between gap-4 border-t border-border pt-3">
          <p className="hidden font-mono text-[8px] text-muted-foreground sm:block">Production binding is immutable after creation.</p>
          <div className="ml-auto flex gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={pending}>Create draft</Button>
          </div>
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
          <Plus className="h-3.5 w-3.5" />
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
            className="rounded-container border border-border bg-surface/40 py-10"
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
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
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
                    <ResourcePill tone="primary">Production</ResourcePill>
                    <ResourcePill>Release {surface.target_release_id.slice(0, 8)}</ResourcePill>
                    <ResourcePill>{surface.allowed_origins.length} {surface.allowed_origins.length === 1 ? 'origin' : 'origins'}</ResourcePill>
                  </>
                )}
                footer={<span className="truncate font-mono text-[8px]">{surface.public_id}</span>}
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
