import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Bot, Check, MessageSquare, Network, Plus } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  Button,
  Field,
  FieldDescription,
  FieldLabel,
  Input,
  SectionBlock,
  Select,
  TechnicalListItem,
  Textarea,
} from '@woobe/ui'

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
  icon: React.ReactNode
  onClick: (type: ChatSurfaceTargetType) => void
}) {
  return (
    <TechnicalListItem
      label={title}
      description={description}
      selected={active}
      aria-pressed={active}
      leading={(
        <span className="flex h-control-segment w-control-segment items-center justify-center rounded-control border border-border bg-control text-primary-light">
          {icon}
        </span>
      )}
      trailing={active ? <Check className="h-icon-sm w-icon-sm text-primary-light" /> : null}
      onClick={() => onClick(type)}
    />
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
    <Dialog
      open
      onClose={onClose}
      title="Create ChatSurface"
      className="max-w-dialog-wide"
      contentClassName="p-0"
      scrollMode="content"
    >
      <form onSubmit={(event) => void submit(event)} className="grid min-h-0">
        <div className="grid gap-ui-md p-ui-panel-inset">
          <SectionBlock
            title="Surface identity"
            description="Name the embedded conversation and bind it to one immutable Production target."
            density="compact"
          >
            <div className="grid gap-ui-md lg:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="surface-name">Name</FieldLabel>
                <Input
                  id="surface-name"
                  autoFocus
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Product support chat"
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="surface-target">Production target</FieldLabel>
                <Select
                  id="surface-target"
                  value={targetId}
                  onChange={(event) => setTargetId(event.target.value)}
                  placeholder="Select target"
                  options={targets.map((target) => ({ value: target.id, label: target.name }))}
                />
              </Field>
            </div>
            <div className="mt-ui-md grid gap-ui-sm sm:grid-cols-2">
              <TargetTypeChoice
                type="agent"
                active={targetType === 'agent'}
                title="Agent"
                description="Expose one Production Agent through the Surface."
                icon={<Bot className="h-icon w-icon" />}
                onClick={(next) => { setTargetType(next); setTargetId('') }}
              />
              <TargetTypeChoice
                type="network"
                active={targetType === 'network'}
                title="Network"
                description="Expose one Production Network through the Surface."
                icon={<Network className="h-icon w-icon" />}
                onClick={(next) => { setTargetType(next); setTargetId('') }}
              />
            </div>
          </SectionBlock>

          <SectionBlock
            title="Origin access"
            description="Authorize the exact browser origin allowed to request ChatSurface Sessions."
            density="compact"
          >
            <Field>
              <FieldLabel htmlFor="surface-origin">Allowed origin</FieldLabel>
              <Input
                id="surface-origin"
                value={origin}
                onChange={(event) => setOrigin(event.target.value)}
                placeholder="https://app.example.com"
              />
              <FieldDescription>Exact HTTPS origin. Local HTTP is accepted only when enabled by the deployment.</FieldDescription>
            </Field>
          </SectionBlock>

          <SectionBlock
            title="Embed appearance"
            description="Initial visual identity. Fine-grained appearance remains editable after creation."
            density="compact"
          >
            <div className="grid gap-ui-md sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="surface-display-title">Display title</FieldLabel>
                <Input
                  id="surface-display-title"
                  value={displayTitle}
                  onChange={(event) => setDisplayTitle(event.target.value)}
                  placeholder={name.trim() || 'Woobe'}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="surface-theme">Theme</FieldLabel>
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
              </Field>
              <Field>
                <FieldLabel htmlFor="surface-color">Primary color</FieldLabel>
                <div className="flex h-control items-center gap-ui-sm rounded-control border border-border bg-control px-ui-sm">
                  <input
                    id="surface-color"
                    type="color"
                    value={primaryColor}
                    onChange={(event) => setPrimaryColor(event.target.value.toUpperCase())}
                    className="h-control-xs w-control-segment shrink-0 rounded-technical border border-border bg-control p-ui-hairline"
                  />
                  <code className="font-mono text-system-meta text-muted-foreground">{primaryColor}</code>
                </div>
              </Field>
              <Field>
                <FieldLabel htmlFor="surface-placeholder">Placeholder</FieldLabel>
                <Input
                  id="surface-placeholder"
                  value={placeholder}
                  onChange={(event) => setPlaceholder(event.target.value)}
                />
              </Field>
              <Field className="sm:col-span-2">
                <FieldLabel htmlFor="surface-welcome">Welcome message</FieldLabel>
                <Textarea
                  id="surface-welcome"
                  value={welcomeMessage}
                  onChange={(event) => setWelcomeMessage(event.target.value)}
                  rows={3}
                  maxLength={500}
                  placeholder="How can I help?"
                  className="min-h-textarea-compact"
                />
                <FieldDescription>Optional initial assistant message shown before the first user message.</FieldDescription>
              </Field>
            </div>
          </SectionBlock>
        </div>

        <div className="flex items-center justify-between gap-ui-md border-t border-border bg-surface/95 px-ui-panel-inset py-ui-md">
          <p className="hidden font-mono text-system-meta text-muted-foreground sm:block">Production binding is immutable after creation.</p>
          <div className="ml-auto flex gap-ui-sm">
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
          <Plus className="h-icon w-icon" />
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
            icon={<MessageSquare className="h-icon-lg w-icon-lg" />}
            title="Publish your first ChatSurface"
            description="Choose a Production Agent or Network, authorize an exact origin and generate a backend-only Access Key."
            action={(
              <Button type="button" size="sm" onClick={() => setCreating(true)}>
                Publish ChatSurface
              </Button>
            )}
          />
        ) : (
          <div className="grid grid-cols-1 gap-ui-md md:grid-cols-2 xl:grid-cols-3">
            {surfaces.map((surface) => (
              <ResourceCard
                key={surface.id}
                aria-label={`Open ChatSurface ${surface.name}`}
                onClick={() => setSelectedSurfaceId(surface.id)}
                icon={<MessageSquare className="h-icon-lg w-icon-lg" />}
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
                footer={<span className="truncate font-mono text-system-meta">{surface.public_id}</span>}
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
