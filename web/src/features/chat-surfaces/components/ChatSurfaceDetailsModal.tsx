import { useEffect, useRef, useState } from 'react'
import {
  Activity,
  Archive,
  Copy,
  Gauge,
  Globe,
  Info,
  KeyRound,
  MessageSquare,
  Palette,
  PanelTop,
  Plus,
  Power,
  RefreshCw,
  RotateCw,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  Square,
  TextCursorInput,
  type LucideIcon,
} from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import {
  ChatSurfaceAppearanceEditor,
  type ChatSurfaceAppearanceSection,
} from '@/features/chat-surfaces/components/ChatSurfaceAppearanceEditor'
import { ChatSurfaceAppearancePreview } from '@/features/chat-surfaces/components/ChatSurfaceAppearancePreview'
import { ChatSurfaceLiveTestDialog } from '@/features/chat-surfaces/components/ChatSurfaceLiveTestDialog'
import {
  useChatSurface,
  useChatSurfaceAccessKeys,
  useChatSurfaceLifecycle,
  useCreateChatSurfaceKey,
  useRefreshChatSurfaceRelease,
  useRevokeChatSurfaceKey,
  useRotateChatSurfaceKey,
  useUpdateChatSurface,
} from '@/features/chat-surfaces/hooks'
import type {
  ChatSurface,
  ChatSurfaceAccessKey,
  ChatSurfaceAppearance,
} from '@/features/chat-surfaces/types'
import { cn } from '@/lib/utils'

interface ChatSurfaceDetailsModalProps {
  open: boolean
  surfaceId: string | null
  projectId: string
  targetName: string
  onClose: () => void
}

interface SurfaceFormState {
  name: string
  description: string
  allowedOrigins: string[]
  appearance: ChatSurfaceAppearance
  requestsPerMinute: string
  maxConcurrentRuns: string
  sessionTokenTtlSeconds: string
}

type DetailsSection =
  | 'overview'
  | 'origins'
  | 'appearance-general'
  | 'appearance-header'
  | 'appearance-surface'
  | 'appearance-messages'
  | 'appearance-composer'
  | 'appearance-send-button'
  | 'appearance-activity'
  | 'runtime'
  | 'release'
  | 'keys'

interface SidebarItem {
  id: DetailsSection
  label: string
  icon: LucideIcon
  indent?: boolean
}

const configurationItems: SidebarItem[] = [
  { id: 'overview', label: 'Overview', icon: Info },
  { id: 'origins', label: 'Origins', icon: Globe },
]

const appearanceItems: SidebarItem[] = [
  { id: 'appearance-general', label: 'General', icon: Palette, indent: true },
  { id: 'appearance-header', label: 'Header', icon: PanelTop, indent: true },
  { id: 'appearance-surface', label: 'Surface', icon: Square, indent: true },
  { id: 'appearance-messages', label: 'Messages', icon: MessageSquare, indent: true },
  { id: 'appearance-composer', label: 'Composer', icon: TextCursorInput, indent: true },
  { id: 'appearance-send-button', label: 'Send button', icon: Send, indent: true },
  { id: 'appearance-activity', label: 'Activity', icon: Activity, indent: true },
]

const operationItems: SidebarItem[] = [
  { id: 'runtime', label: 'Runtime', icon: Gauge },
  { id: 'release', label: 'Release', icon: RefreshCw },
  { id: 'keys', label: 'Access Keys', icon: KeyRound },
]

function surfaceForm(surface: ChatSurface): SurfaceFormState {
  return {
    name: surface.name,
    description: surface.description ?? '',
    allowedOrigins: [...surface.allowed_origins],
    appearance: { ...surface.appearance_config },
    requestsPerMinute: String(surface.requests_per_minute),
    maxConcurrentRuns: String(surface.max_concurrent_runs),
    sessionTokenTtlSeconds: String(surface.session_token_ttl_seconds),
  }
}

function snapshotForm(form: SurfaceFormState): string {
  return JSON.stringify(form)
}

function formatDate(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : 'Never'
}

function shortId(value: string): string {
  return value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value
}

function normalizeOriginInput(value: string): { value?: string; error?: string } {
  const raw = value.trim()
  if (!raw) return { error: 'Enter an origin first' }

  let parsed: URL
  try {
    parsed = new URL(raw)
  } catch {
    return { error: 'Enter a valid absolute HTTP(S) origin' }
  }

  if (!['http:', 'https:'].includes(parsed.protocol)) {
    return { error: 'Origin must use HTTP or HTTPS' }
  }
  if (parsed.username || parsed.password) {
    return { error: 'Origin cannot include credentials' }
  }
  if (parsed.pathname !== '/' || parsed.search || parsed.hash) {
    return { error: 'Use an exact origin without path, query or fragment' }
  }
  if (parsed.hostname.includes('*')) {
    return { error: 'Wildcards are not allowed' }
  }

  return { value: parsed.origin }
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">
      {children}
    </span>
  )
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-border/80 bg-background/55 p-4">
      <p className="text-[11px] uppercase tracking-wider text-muted">{label}</p>
      <p className="mt-1 break-words text-sm font-medium text-white">{value}</p>
    </div>
  )
}

function SidebarSectionTitle({ children }: { children: string }) {
  return (
    <p className="hidden px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted/80 md:block">
      {children}
    </p>
  )
}

function SidebarNavButton({
  item,
  active,
  onClick,
}: {
  item: SidebarItem
  active: boolean
  onClick: () => void
}) {
  const Icon = item.icon

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'group flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-[border-color,background-color,color] md:w-full md:text-sm',
        item.indent && 'md:pl-5',
        active
          ? 'border-primary/35 bg-primary/10 text-primary-light'
          : 'border-transparent text-muted hover:border-primary/20 hover:bg-background/70 hover:text-white',
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="whitespace-nowrap md:truncate">{item.label}</span>
    </button>
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
    <Dialog open onClose={onClose} title="ChatSurface Access Key" className="max-w-xl">
      <div className="space-y-4">
        <div className="rounded-xl border border-amber-500/25 bg-amber-500/10 p-4">
          <p className="text-sm font-medium text-amber-100">Copy this secret now</p>
          <p className="mt-1 text-xs leading-5 text-amber-100/75">
            The secret is shown only once. Store it in the integrator backend and never expose it in browser code.
          </p>
        </div>
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

export function ChatSurfaceDetailsModal({
  open,
  surfaceId,
  projectId,
  targetName,
  onClose,
}: ChatSurfaceDetailsModalProps) {
  const surfaceQuery = useChatSurface(surfaceId ?? undefined, projectId)
  const keysQuery = useChatSurfaceAccessKeys(surfaceId ?? undefined)
  const updateMutation = useUpdateChatSurface()
  const releaseMutation = useRefreshChatSurfaceRelease()
  const lifecycleMutation = useChatSurfaceLifecycle()
  const createKeyMutation = useCreateChatSurfaceKey()
  const rotateKeyMutation = useRotateChatSurfaceKey()
  const revokeKeyMutation = useRevokeChatSurfaceKey()

  const [form, setForm] = useState<SurfaceFormState | null>(null)
  const [baseline, setBaseline] = useState('')
  const [originInput, setOriginInput] = useState('')
  const [keyName, setKeyName] = useState('Default ChatSurface key')
  const [revealedKey, setRevealedKey] = useState<ChatSurfaceAccessKey | null>(null)
  const [discardOpen, setDiscardOpen] = useState(false)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [revokeCandidate, setRevokeCandidate] = useState<ChatSurfaceAccessKey | null>(null)
  const [liveTestOpen, setLiveTestOpen] = useState(false)
  const [activeSection, setActiveSection] = useState<DetailsSection>('overview')
  const initializedSurfaceRef = useRef<string | null>(null)

  const surface = surfaceQuery.data
  const accessKeys = keysQuery.data ?? []
  const hasChanges = Boolean(form && baseline && snapshotForm(form) !== baseline)
  const archived = surface?.status === 'archived'
  const liveTestDisabledReason = !surface
    ? null
    : hasChanges
      ? 'Save configuration changes before starting a live test.'
      : surface.status === 'archived'
        ? 'Archived ChatSurfaces cannot be tested.'
        : surface.status !== 'active'
          ? 'Activate the ChatSurface before starting a live test.'
          : null
  const busy = updateMutation.isPending
    || releaseMutation.isPending
    || lifecycleMutation.isPending
    || createKeyMutation.isPending
    || rotateKeyMutation.isPending
    || revokeKeyMutation.isPending

  useEffect(() => {
    if (!open) {
      initializedSurfaceRef.current = null
      setLiveTestOpen(false)
      return
    }
    if (!surface || initializedSurfaceRef.current === surface.id) return

    const next = surfaceForm(surface)
    setForm(next)
    setBaseline(snapshotForm(next))
    setOriginInput('')
    setKeyName('Default ChatSurface key')
    setRevealedKey(null)
    setDiscardOpen(false)
    setArchiveOpen(false)
    setRevokeCandidate(null)
    setLiveTestOpen(false)
    setActiveSection('overview')
    initializedSurfaceRef.current = surface.id
  }, [open, surface])

  const finishClose = () => {
    if (busy) return
    initializedSurfaceRef.current = null
    setForm(null)
    setBaseline('')
    setDiscardOpen(false)
    setArchiveOpen(false)
    setRevokeCandidate(null)
    setRevealedKey(null)
    setLiveTestOpen(false)
    setActiveSection('overview')
    onClose()
  }

  const requestClose = () => {
    if (busy) return
    if (hasChanges) {
      setDiscardOpen(true)
      return
    }
    finishClose()
  }

  const requireCleanForm = () => {
    if (!hasChanges) return true
    toast.error('Save or discard the pending configuration changes first')
    return false
  }

  const addOrigin = () => {
    if (!form || archived) return
    const normalized = normalizeOriginInput(originInput)
    if (!normalized.value) {
      toast.error(normalized.error ?? 'Invalid origin')
      return
    }
    if (form.allowedOrigins.includes(normalized.value)) {
      toast.info('This origin is already allowed')
      return
    }
    if (form.allowedOrigins.length >= 32) {
      toast.error('A ChatSurface can contain at most 32 allowed origins')
      return
    }
    setForm({ ...form, allowedOrigins: [...form.allowedOrigins, normalized.value] })
    setOriginInput('')
  }

  const save = async () => {
    if (!surface || !form || archived) return
    if (originInput.trim()) {
      toast.error('Add or clear the pending origin before saving')
      return
    }

    const name = form.name.trim()
    const title = form.appearance.title.trim()
    const placeholder = form.appearance.placeholder.trim()
    const requestsPerMinute = Number(form.requestsPerMinute)
    const maxConcurrentRuns = Number(form.maxConcurrentRuns)
    const sessionTokenTtlSeconds = Number(form.sessionTokenTtlSeconds)

    if (!name) {
      toast.error('ChatSurface name is required')
      return
    }
    if (!title || !placeholder) {
      toast.error('Display title and placeholder are required')
      return
    }
    if (surface.status === 'active' && form.allowedOrigins.length === 0) {
      toast.error('An active ChatSurface requires at least one allowed origin')
      return
    }
    if (!Number.isInteger(requestsPerMinute) || requestsPerMinute < 1 || requestsPerMinute > 10_000) {
      toast.error('Requests per minute must be between 1 and 10000')
      return
    }
    if (!Number.isInteger(maxConcurrentRuns) || maxConcurrentRuns < 1 || maxConcurrentRuns > 100) {
      toast.error('Maximum concurrent Runs must be between 1 and 100')
      return
    }
    if (!Number.isInteger(sessionTokenTtlSeconds) || sessionTokenTtlSeconds < 60 || sessionTokenTtlSeconds > 3600) {
      toast.error('Session token TTL must be between 60 and 3600 seconds')
      return
    }

    try {
      const updated = await updateMutation.mutateAsync({
        surfaceId: surface.id,
        input: {
          name,
          description: form.description.trim() || null,
          allowed_origins: form.allowedOrigins,
          appearance_config: {
            ...form.appearance,
            title,
            placeholder,
            welcome_message: form.appearance.welcome_message?.trim() || null,
          },
          requests_per_minute: requestsPerMinute,
          max_concurrent_runs: maxConcurrentRuns,
          session_token_ttl_seconds: sessionTokenTtlSeconds,
        },
      })
      const next = surfaceForm(updated)
      setForm(next)
      setBaseline(snapshotForm(next))
      toast.success('ChatSurface configuration updated')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to update ChatSurface')
    }
  }

  const runLifecycle = async (action: 'activate' | 'disable' | 'archive') => {
    if (!surface || !requireCleanForm()) return
    try {
      await lifecycleMutation.mutateAsync({ surfaceId: surface.id, action })
      if (action === 'archive') {
        setArchiveOpen(false)
        toast.success('ChatSurface archived')
      } else {
        toast.success(action === 'activate' ? 'ChatSurface activated' : 'ChatSurface disabled')
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to update ChatSurface lifecycle')
    }
  }

  const refreshRelease = async () => {
    if (!surface || !requireCleanForm()) return
    try {
      const previous = surface.target_release_id
      const updated = await releaseMutation.mutateAsync(surface.id)
      toast.success(
        updated.target_release_id === previous
          ? 'ChatSurface already uses the current Production Release'
          : 'New Sessions will use the current Production Release',
      )
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to refresh Production Release')
    }
  }

  const createKey = async () => {
    if (!surface || archived || !requireCleanForm()) return
    const name = keyName.trim()
    if (!name) {
      toast.error('Access Key name is required')
      return
    }
    try {
      const created = await createKeyMutation.mutateAsync({ surfaceId: surface.id, name })
      setRevealedKey(created)
      toast.success('Access Key created')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to create Access Key')
    }
  }

  const rotateKey = async (accessKey: ChatSurfaceAccessKey) => {
    if (!surface || archived || !requireCleanForm()) return
    try {
      const replacement = await rotateKeyMutation.mutateAsync({
        surfaceId: surface.id,
        apiKeyId: accessKey.id,
      })
      setRevealedKey(replacement)
      toast.success('Access Key rotated')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to rotate Access Key')
    }
  }

  const revokeKey = async () => {
    if (!surface || !revokeCandidate || !requireCleanForm()) return
    try {
      await revokeKeyMutation.mutateAsync({
        surfaceId: surface.id,
        apiKeyId: revokeCandidate.id,
      })
      setRevokeCandidate(null)
      toast.success('Access Key revoked')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to revoke Access Key')
    }
  }

  const overviewContent = surface && form ? (
    <div className="space-y-5">
      <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
        <h3 className="text-sm font-semibold text-white">General</h3>
        <p className="mt-1 text-xs text-muted">Identity and description shown to operators managing this Surface.</p>
        <div className="mt-5 space-y-4">
          <label className="block">
            <FieldLabel>Name</FieldLabel>
            <Input
              value={form.name}
              disabled={archived}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </label>
          <label className="block">
            <FieldLabel>Description</FieldLabel>
            <Textarea
              value={form.description}
              disabled={archived}
              rows={4}
              maxLength={2000}
              placeholder="Where this embedded conversation is used"
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </label>
        </div>
      </section>

      <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
        <h3 className="text-sm font-semibold text-white">Immutable binding</h3>
        <p className="mt-1 text-xs text-muted">These fields define the published boundary and are not editable after creation.</p>
        <div className="mt-4 grid min-w-0 gap-3 sm:grid-cols-2">
          <ReadOnlyField label="Target" value={`${surface.target_type === 'agent' ? 'Agent' : 'Network'} · ${targetName}`} />
          <ReadOnlyField label="Environment" value="Production" />
          <ReadOnlyField label="Public ID" value={surface.public_id} />
          <ReadOnlyField label="Access mode" value="Backend managed" />
        </div>
      </section>

      <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Lifecycle</h3>
            <p className="mt-1 max-w-xl text-xs leading-5 text-muted">
              Activate or disable the public ChatSurface without changing its immutable target binding.
            </p>
          </div>
          <StatusBadge status={surface.status} size="compact" />
        </div>
        {surface.status === 'archived' ? (
          <p className="mt-4 text-sm leading-6 text-muted">Archived Surfaces are read-only and cannot be reactivated.</p>
        ) : (
          <div className="mt-5 flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              loading={lifecycleMutation.isPending}
              onClick={() => void runLifecycle(surface.status === 'active' ? 'disable' : 'activate')}
            >
              <Power className="mr-2 h-3.5 w-3.5" />
              {surface.status === 'active' ? 'Disable ChatSurface' : 'Activate ChatSurface'}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="text-red-300 hover:text-red-200"
              onClick={() => {
                if (!requireCleanForm()) return
                setArchiveOpen(true)
              }}
            >
              <Archive className="mr-2 h-3.5 w-3.5" />
              Archive
            </Button>
          </div>
        )}
      </section>
    </div>
  ) : null

  const originsContent = surface && form ? (
    <div className="space-y-5">
      <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
        <h3 className="text-sm font-semibold text-white">Allowed origins</h3>
        <p className="mt-1 text-xs leading-5 text-muted">
          Session tokens are issued for exact host origins. Wildcards, paths, queries and fragments are rejected by the API.
        </p>

        <div className="mt-5 space-y-2">
          {form.allowedOrigins.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-background/45 px-4 py-8 text-center text-sm text-muted">
              No origin configured.
            </div>
          ) : form.allowedOrigins.map((origin) => (
            <div key={origin} className="flex min-w-0 items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/55 px-3 py-2.5">
              <code className="min-w-0 truncate text-xs text-slate-200">{origin}</code>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="shrink-0"
                disabled={archived}
                onClick={() => setForm({
                  ...form,
                  allowedOrigins: form.allowedOrigins.filter((item) => item !== origin),
                })}
              >
                Remove
              </Button>
            </div>
          ))}
        </div>

        <div className="mt-4 flex min-w-0 flex-col gap-2 sm:flex-row">
          <Input
            value={originInput}
            disabled={archived}
            placeholder="https://app.example.com"
            onChange={(event) => setOriginInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                addOrigin()
              }
            }}
          />
          <Button type="button" variant="outline" className="shrink-0" disabled={archived} onClick={addOrigin}>
            <Plus className="mr-2 h-4 w-4" />
            Add origin
          </Button>
        </div>
        <p className="mt-2 text-[11px] leading-5 text-muted">
          HTTP origins require insecure origins to be enabled on the Woobe instance. HTTPS is recommended for production.
        </p>
      </section>
    </div>
  ) : null

  const appearanceSection = activeSection.startsWith('appearance-')
    ? activeSection.replace('appearance-', '') as ChatSurfaceAppearanceSection
    : null

  const appearanceContent = surface && form && appearanceSection ? (
    <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0">
        <ChatSurfaceAppearanceEditor
          appearance={form.appearance}
          section={appearanceSection}
          disabled={archived}
          onChange={(appearance) => setForm({ ...form, appearance })}
        />
      </div>

      <div className="min-w-0 self-start xl:sticky xl:top-0">
        <ChatSurfaceAppearancePreview
          appearance={form.appearance}
          testDisabledReason={liveTestDisabledReason}
          onTest={() => {
            if (liveTestDisabledReason) {
              toast.error(liveTestDisabledReason)
              return
            }
            setLiveTestOpen(true)
          }}
        />
      </div>
    </div>
  ) : null

  const runtimeContent = form ? (
    <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
      <h3 className="text-sm font-semibold text-white">Runtime limits</h3>
      <p className="mt-1 text-xs text-muted">Operational limits enforced for this ChatSurface.</p>
      <div className="mt-5 grid gap-4 sm:grid-cols-3">
        <label className="block min-w-0">
          <FieldLabel>Requests / minute</FieldLabel>
          <Input
            type="number"
            min={1}
            max={10000}
            value={form.requestsPerMinute}
            disabled={archived}
            onChange={(event) => setForm({ ...form, requestsPerMinute: event.target.value })}
          />
          <span className="mt-1 block text-[11px] text-muted">1–10000</span>
        </label>
        <label className="block min-w-0">
          <FieldLabel>Concurrent Runs</FieldLabel>
          <Input
            type="number"
            min={1}
            max={100}
            value={form.maxConcurrentRuns}
            disabled={archived}
            onChange={(event) => setForm({ ...form, maxConcurrentRuns: event.target.value })}
          />
          <span className="mt-1 block text-[11px] text-muted">1–100</span>
        </label>
        <label className="block min-w-0">
          <FieldLabel>Session token TTL</FieldLabel>
          <Input
            type="number"
            min={60}
            max={3600}
            value={form.sessionTokenTtlSeconds}
            disabled={archived}
            onChange={(event) => setForm({ ...form, sessionTokenTtlSeconds: event.target.value })}
          />
          <span className="mt-1 block text-[11px] text-muted">60–3600 seconds</span>
        </label>
      </div>
    </section>
  ) : null

  const releaseContent = surface ? (
    <div className="space-y-5">
      <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Production binding</h3>
            <p className="mt-1 max-w-xl text-xs leading-5 text-muted">
              New Sessions use the immutable Release pinned here. Existing Sessions keep the Release captured when they were created.
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            className="shrink-0"
            disabled={archived || releaseMutation.isPending}
            loading={releaseMutation.isPending}
            onClick={() => void refreshRelease()}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Use current Production Release
          </Button>
        </div>
        <div className="mt-5 grid min-w-0 gap-3 sm:grid-cols-2">
          <ReadOnlyField label="Target" value={`${surface.target_type === 'agent' ? 'Agent' : 'Network'} · ${targetName}`} />
          <ReadOnlyField label="Pinned Release" value={surface.target_release_id} />
        </div>
      </section>
    </div>
  ) : null

  const accessKeysContent = surface ? (
    <div className="space-y-5">
      <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Access Keys</h3>
            <p className="mt-1 max-w-xl text-xs leading-5 text-muted">
              Backend-only credentials used by the integrator to create Sessions and issue browser Session tokens.
            </p>
          </div>
          <div className="flex min-w-0 w-full gap-2 sm:w-auto">
            <Input
              value={keyName}
              disabled={archived}
              maxLength={255}
              placeholder="Key name"
              className="min-w-0 sm:w-64"
              onChange={(event) => setKeyName(event.target.value)}
            />
            <Button
              type="button"
              className="shrink-0"
              disabled={archived}
              loading={createKeyMutation.isPending}
              onClick={() => void createKey()}
            >
              <Plus className="mr-2 h-4 w-4" />
              Create
            </Button>
          </div>
        </div>

        <div className="mt-5">
          {keysQuery.isLoading ? (
            <LoadingState message="Loading Access Keys" variant="inline" />
          ) : keysQuery.isError ? (
            <ErrorState error={keysQuery.error} onRetry={keysQuery.refetch} />
          ) : accessKeys.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-background/45 px-4 py-10 text-center">
              <KeyRound className="mx-auto h-5 w-5 text-muted" />
              <p className="mt-3 text-sm font-medium text-white">No Access Keys</p>
              <p className="mt-1 text-xs text-muted">Create a backend credential when the integrator is ready.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {accessKeys.map((accessKey) => {
                const active = accessKey.status === 'active'
                return (
                  <div key={accessKey.id} className="grid min-w-0 gap-3 rounded-xl border border-border/70 bg-background/55 p-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-medium text-white">{accessKey.name}</p>
                        <StatusBadge status={accessKey.status} size="compact" />
                      </div>
                      <p className="mt-1 truncate font-mono text-xs text-muted">{accessKey.prefix}</p>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
                        <span>Created · {formatDate(accessKey.created_at)}</span>
                        <span>Last used · {formatDate(accessKey.last_used_at)}</span>
                        {accessKey.expires_at && <span>Expires · {formatDate(accessKey.expires_at)}</span>}
                      </div>
                    </div>
                    <div className="flex flex-wrap justify-end gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={!active || archived}
                        loading={rotateKeyMutation.isPending}
                        onClick={() => void rotateKey(accessKey)}
                      >
                        <RotateCw className="mr-2 h-3.5 w-3.5" />
                        Rotate
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        disabled={!active}
                        onClick={() => {
                          if (!requireCleanForm()) return
                          setRevokeCandidate(accessKey)
                        }}
                      >
                        Revoke
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </section>
    </div>
  ) : null

  const currentContent = activeSection === 'overview'
    ? overviewContent
    : activeSection === 'origins'
      ? originsContent
      : appearanceSection
        ? appearanceContent
        : activeSection === 'runtime'
          ? runtimeContent
          : activeSection === 'release'
            ? releaseContent
            : accessKeysContent

  return (
    <>
      <Dialog
        open={open}
        onClose={requestClose}
        title="ChatSurface details"
        className="flex h-[min(900px,calc(100svh-2rem))] max-w-7xl flex-col overflow-hidden"
        contentClassName="min-h-0 flex-1 p-0"
      >
        {surfaceQuery.isLoading && !surface ? (
          <div className="p-10">
            <LoadingState message="Loading ChatSurface" variant="panel" />
          </div>
        ) : surfaceQuery.isError && !surface ? (
          <div className="p-8">
            <ErrorState error={surfaceQuery.error} onRetry={surfaceQuery.refetch} />
          </div>
        ) : surface && form ? (
          <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)] md:grid-cols-[230px_minmax(0,1fr)] md:grid-rows-1">
            <aside className="flex min-h-0 min-w-0 flex-col border-b border-border bg-background/35 md:border-b-0 md:border-r">
              <div className="hidden border-b border-border p-4 md:block">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light">
                    <MessageSquare className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex min-w-0 items-center gap-2">
                      <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-white">{surface.name}</h3>
                      <StatusBadge status={surface.status} size="compact" />
                    </div>
                    <p className="mt-1 truncate text-xs text-muted" title={targetName}>
                      Production · {surface.target_type === 'agent' ? 'Agent' : 'Network'} · {targetName}
                    </p>
                    <button
                      type="button"
                      className="mt-2 flex max-w-full items-center gap-1.5 font-mono text-[11px] text-muted hover:text-white"
                      onClick={() => {
                        void navigator.clipboard.writeText(surface.public_id)
                        toast.success('Public ID copied')
                      }}
                    >
                      <span className="truncate">{surface.public_id}</span>
                      <Copy className="h-3 w-3 shrink-0" />
                    </button>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-border/70 pt-3 text-[11px] text-muted">
                  <span>{form.allowedOrigins.length} origins</span>
                  <span className="font-mono" title={surface.target_release_id}>{shortId(surface.target_release_id)}</span>
                </div>
              </div>

              <nav className="flex min-w-0 gap-1 overflow-x-auto p-2 md:block md:flex-1 md:space-y-5 md:overflow-y-auto md:p-3">
                <div className="contents md:block md:space-y-2">
                  <SidebarSectionTitle>Configuration</SidebarSectionTitle>
                  <div className="contents md:block md:space-y-1">
                    {configurationItems.map((item) => (
                      <SidebarNavButton
                        key={item.id}
                        item={item}
                        active={activeSection === item.id}
                        onClick={() => setActiveSection(item.id)}
                      />
                    ))}
                  </div>
                </div>

                <div className="contents md:block md:space-y-2">
                  <SidebarSectionTitle>Appearance</SidebarSectionTitle>
                  <div className="contents md:block md:space-y-1">
                    {appearanceItems.map((item) => (
                      <SidebarNavButton
                        key={item.id}
                        item={item}
                        active={activeSection === item.id}
                        onClick={() => setActiveSection(item.id)}
                      />
                    ))}
                  </div>
                </div>

                <div className="contents md:block md:space-y-2">
                  <SidebarSectionTitle>Operate</SidebarSectionTitle>
                  <div className="contents md:block md:space-y-1">
                    {operationItems.map((item) => (
                      <SidebarNavButton
                        key={item.id}
                        item={item}
                        active={activeSection === item.id}
                        onClick={() => setActiveSection(item.id)}
                      />
                    ))}
                  </div>
                </div>
              </nav>
            </aside>

            <main className="flex min-h-0 min-w-0 flex-col overflow-hidden">
              <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain p-4 sm:p-5 lg:p-6">
                {currentContent}
              </div>
              <div className="flex shrink-0 flex-col-reverse gap-2 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur sm:flex-row sm:items-center sm:justify-between lg:px-6">
                <p className="text-[11px] text-muted">
                  {archived ? 'Archived · configuration is read-only' : hasChanges ? 'Unsaved configuration changes' : `Updated · ${formatDate(surface.updated_at)}`}
                </p>
                <div className="flex flex-wrap justify-end gap-2">
                  <Button type="button" variant="outline" disabled={busy} onClick={requestClose}>Close</Button>
                  <Button
                    type="button"
                    disabled={archived || !hasChanges}
                    loading={updateMutation.isPending}
                    onClick={() => void save()}
                  >
                    <ShieldCheck className="mr-2 h-4 w-4" />
                    Save changes
                  </Button>
                </div>
              </div>
            </main>
          </div>
        ) : null}
      </Dialog>

      <Dialog open={discardOpen} onClose={() => setDiscardOpen(false)} title="Discard changes?" className="max-w-md">
        <div className="space-y-5">
          <p className="text-sm leading-6 text-muted">The unsaved ChatSurface configuration will be lost.</p>
          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <Button type="button" variant="outline" onClick={() => setDiscardOpen(false)}>Keep editing</Button>
            <Button type="button" variant="destructive" onClick={finishClose}>Discard</Button>
          </div>
        </div>
      </Dialog>

      <Dialog open={archiveOpen} onClose={() => setArchiveOpen(false)} title="Archive ChatSurface?" className="max-w-md">
        <div className="space-y-5">
          <p className="text-sm leading-6 text-muted">
            Archiving is irreversible. Existing Session tokens are invalidated and this ChatSurface cannot be reactivated.
          </p>
          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <Button type="button" variant="outline" disabled={lifecycleMutation.isPending} onClick={() => setArchiveOpen(false)}>Cancel</Button>
            <Button type="button" variant="destructive" loading={lifecycleMutation.isPending} onClick={() => void runLifecycle('archive')}>Archive</Button>
          </div>
        </div>
      </Dialog>

      <Dialog open={Boolean(revokeCandidate)} onClose={() => setRevokeCandidate(null)} title="Revoke Access Key?" className="max-w-md">
        {revokeCandidate && (
          <div className="space-y-5">
            <div className="rounded-xl border border-border bg-background/55 p-4">
              <p className="text-sm font-medium text-white">{revokeCandidate.name}</p>
              <p className="mt-1 font-mono text-xs text-muted">{revokeCandidate.prefix}</p>
            </div>
            <p className="text-sm leading-6 text-muted">Requests using this credential will stop authenticating immediately.</p>
            <div className="flex justify-end gap-2 border-t border-border pt-4">
              <Button type="button" variant="outline" disabled={revokeKeyMutation.isPending} onClick={() => setRevokeCandidate(null)}>Cancel</Button>
              <Button type="button" variant="destructive" loading={revokeKeyMutation.isPending} onClick={() => void revokeKey()}>Revoke</Button>
            </div>
          </div>
        )}
      </Dialog>

      {surface && revealedKey ? (
        <AccessKeyReveal surface={surface} accessKey={revealedKey} onClose={() => setRevealedKey(null)} />
      ) : null}

      {surface ? (
        <ChatSurfaceLiveTestDialog
          open={liveTestOpen}
          surface={surface}
          targetName={targetName}
          onClose={() => setLiveTestOpen(false)}
        />
      ) : null}
    </>
  )
}