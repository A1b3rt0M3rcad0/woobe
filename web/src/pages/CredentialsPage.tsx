import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertTriangle, Cable, Cpu, Database, Pencil, Search, ShieldOff, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { CreateResourceCard } from '@/components/common/CreateResourceCard'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { useCredentials, useUpdateCredential } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'
import { get } from '@/lib/api/client'

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible',
  openrouter: 'OpenRouter',
}

type AgentSummary = {
  id: string
  name: string
  status?: string
  provider_model_id?: string | null
  fallback_provider_model_id?: string | null
  provider_credential_id?: string | null
  fallback_credential_id?: string | null
}

type ReleaseSummary = {
  id: string
  name?: string | null
  version?: string
  status?: string
  provider_model_id?: string | null
  fallback_provider_model_id?: string | null
  provider_credential_id?: string | null
  fallback_credential_id?: string | null
}

type UsageItem = {
  type: string
  id: string
  name?: string | null
  field?: string
  status?: string
  version?: string
}

type ConfirmState = null | {
  kind: 'archive' | 'revoke'
  credential: ProviderCredential
  usage: UsageItem[]
}

function providerLabel(provider?: string | null) {
  return provider ? providerLabels[provider] || provider : 'Unknown provider'
}

function metadataOf(item?: { metadata?: Record<string, unknown> | Record<string, string> | null } | null): Record<string, unknown> {
  return (item?.metadata || {}) as Record<string, unknown>
}

function stringMetadata(value: Record<string, unknown>): Record<string, string> {
  const output: Record<string, string> = {}
  for (const [key, item] of Object.entries(value)) {
    if (item === undefined || item === null || item === '') continue
    output[key] = String(item)
  }
  return output
}

function isEmbeddingModel(model: ProviderModel) {
  const metadata = metadataOf(model)
  const capability = String(metadata.capability || metadata.type || '').trim().toLowerCase()
  if (capability) return capability === 'embedding' || capability === 'embeddings'
  return `${model.name} ${model.model}`.toLowerCase().includes('embed')
}

function isArchived(item?: { status?: string | null } | null) {
  return item?.status === 'archived'
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Never'
}

async function loadUsage(projectId: string) {
  const baseAgents = await get<AgentSummary[]>('/ai/agents', { params: { project_id: projectId } })
  const agents = await Promise.all(
    baseAgents.map(async (agent) => get<AgentSummary>(`/ai/agents/${agent.id}`).catch(() => agent)),
  )
  const releaseGroups = await Promise.all(
    agents.map(async (agent) => get<ReleaseSummary[]>(`/ai/agents/${agent.id}/releases`).catch(() => [])),
  )
  return { agents, releases: releaseGroups.flat() }
}

function usageForCredential(
  credential: ProviderCredential,
  models: ProviderModel[],
  agents: AgentSummary[],
  releases: ReleaseSummary[],
): UsageItem[] {
  const items: UsageItem[] = []
  const modelIds = new Set(
    models
      .filter((model) => model.provider_credential_id === credential.id && !isArchived(model))
      .map((model) => model.id),
  )

  for (const model of models) {
    if (model.provider_credential_id === credential.id && !isArchived(model)) {
      items.push({
        type: isEmbeddingModel(model) ? 'embedding_model' : 'generation_model',
        id: model.id,
        name: model.name,
        field: 'provider_credential_id',
        status: model.status,
      })
    }
  }

  for (const agent of agents) {
    if (agent.status === 'archived') continue
    if (agent.provider_credential_id === credential.id || agent.fallback_credential_id === credential.id) {
      items.push({ type: 'agent', id: agent.id, name: agent.name, field: 'credential', status: agent.status })
    }
    if ((agent.provider_model_id && modelIds.has(agent.provider_model_id)) || (agent.fallback_provider_model_id && modelIds.has(agent.fallback_provider_model_id))) {
      items.push({ type: 'agent', id: agent.id, name: agent.name, field: 'provider_model_id', status: agent.status })
    }
  }

  for (const release of releases) {
    if (!['draft', 'staging', 'production'].includes(release.status || '')) continue
    if (release.provider_credential_id === credential.id || release.fallback_credential_id === credential.id) {
      items.push({ type: 'release', id: release.id, name: release.name, version: release.version, field: 'credential', status: release.status })
    }
    if ((release.provider_model_id && modelIds.has(release.provider_model_id)) || (release.fallback_provider_model_id && modelIds.has(release.fallback_provider_model_id))) {
      items.push({ type: 'release', id: release.id, name: release.name, version: release.version, field: 'provider_model_id', status: release.status })
    }
  }

  const unique = new Map<string, UsageItem>()
  for (const item of items) unique.set(`${item.type}:${item.id}:${item.field || ''}`, item)
  return Array.from(unique.values())
}

function CredentialCard({
  credential,
  generationCount,
  embeddingCount,
  onClick,
}: {
  credential: ProviderCredential
  generationCount: number
  embeddingCount: number
  onClick: () => void
}) {
  const baseUrl = String(metadataOf(credential).base_url || '')
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex min-h-[240px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <span className="flex items-start justify-between gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light shadow-sm">
          <Cable className="h-5 w-5" />
        </span>
        <StatusBadge status={credential.status || 'active'} />
      </span>

      <span className="mt-6 block min-w-0">
        <span className="block truncate text-base font-semibold text-white">{credential.name}</span>
        <span className="mt-2 block truncate text-xs text-muted">{providerLabel(credential.provider)}</span>
        {baseUrl && <span className="mt-1 block truncate text-xs text-muted/75">{baseUrl}</span>}
      </span>

      <span className="my-5 block h-px bg-border/80" />

      <span className="grid gap-2 text-xs text-muted">
        <span className="flex items-center gap-2"><Cpu className="h-3.5 w-3.5" />{generationCount} generation {generationCount === 1 ? 'model' : 'models'}</span>
        <span className="flex items-center gap-2"><Database className="h-3.5 w-3.5" />{embeddingCount} embedding {embeddingCount === 1 ? 'model' : 'models'}</span>
      </span>
    </button>
  )
}

function CredentialDetailsDialog({
  credential,
  attachedModels,
  open,
  onClose,
  onEdit,
  onArchive,
  onRevoke,
}: {
  credential: ProviderCredential | null
  attachedModels: ProviderModel[]
  open: boolean
  onClose: () => void
  onEdit: () => void
  onArchive: () => void
  onRevoke: () => void
}) {
  if (!credential) return null
  const baseUrl = String(metadataOf(credential).base_url || 'Default provider endpoint')
  const generationModels = attachedModels.filter((model) => !isEmbeddingModel(model) && !isArchived(model))
  const embeddingModels = attachedModels.filter((model) => isEmbeddingModel(model) && !isArchived(model))

  return (
    <Dialog open={open} onClose={onClose} title={credential.name} className="max-w-3xl">
      <div className="space-y-5">
        <section className="rounded-xl border border-border/80 bg-surface/60 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">{providerLabel(credential.provider)}</p>
              <p className="mt-1 text-xs text-muted">{baseUrl}</p>
            </div>
            <StatusBadge status={credential.status || 'active'} />
          </div>
          <p className="mt-4 text-xs text-muted">Created · {formatDate(credential.created_at)}</p>
        </section>

        <section className="rounded-xl border border-border/80 bg-background/55 p-4">
          <h3 className="text-sm font-semibold text-white">Connected models</h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Generation</p>
              <div className="mt-2 space-y-2">
                {generationModels.length === 0 ? <p className="text-sm text-muted">No generation models.</p> : generationModels.map((model) => (
                  <div key={model.id} className="rounded-lg border border-border/70 bg-surface/50 px-3 py-2">
                    <p className="truncate text-sm text-white/90">{model.name}</p>
                    <code className="mt-1 block truncate text-xs text-muted">{model.model}</code>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Embedding</p>
              <div className="mt-2 space-y-2">
                {embeddingModels.length === 0 ? <p className="text-sm text-muted">No embedding models.</p> : embeddingModels.map((model) => (
                  <div key={model.id} className="rounded-lg border border-border/70 bg-surface/50 px-3 py-2">
                    <p className="truncate text-sm text-white/90">{model.name}</p>
                    <code className="mt-1 block truncate text-xs text-muted">{model.model}</code>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <div className="flex flex-wrap justify-between gap-3 border-t border-border pt-4">
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={onEdit}>
              <Pencil className="mr-2 h-4 w-4" />
              Edit connection
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={onRevoke} disabled={credential.status === 'revoked'} className="text-amber-200 hover:text-amber-100">
              <ShieldOff className="mr-2 h-4 w-4" />
              Revoke
            </Button>
            <Button type="button" variant="outline" onClick={onArchive} className="text-red-200 hover:text-red-100">
              <Trash2 className="mr-2 h-4 w-4" />
              Archive
            </Button>
          </div>
        </div>
      </div>
    </Dialog>
  )
}

function ImpactDialog({
  state,
  loading,
  onClose,
  onConfirm,
}: {
  state: ConfirmState
  loading: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  if (!state) return null
  const isArchive = state.kind === 'archive'
  const blocked = isArchive && state.usage.length > 0

  return (
    <Dialog open={Boolean(state)} onClose={onClose} title={isArchive ? 'Archive credential' : 'Revoke credential'} className="max-w-2xl">
      <div className="space-y-4">
        <div className="rounded-xl border border-border/80 bg-background/60 p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-amber-400/30 bg-amber-400/10 text-amber-200">
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">{state.credential.name}</p>
              <p className="mt-1 text-sm leading-6 text-muted">
                {isArchive
                  ? 'Archive is blocked while this connection is used by models, agents or active releases.'
                  : 'Revoking stops runtime calls that depend on this connection. Existing configuration is preserved.'}
              </p>
            </div>
          </div>
        </div>

        {state.usage.length > 0 && (
          <div className="rounded-xl border border-border/80 bg-surface/50 p-4">
            <p className="text-sm font-semibold text-white">Current usage</p>
            <div className="scrollbar-thin mt-3 max-h-72 space-y-2 overflow-auto">
              {state.usage.map((item, index) => (
                <div key={`${item.type}-${item.id}-${item.field}-${index}`} className="rounded-lg border border-border/70 bg-background/60 p-3 text-xs text-muted">
                  <p className="font-medium text-white">{item.type} · {item.name || item.version || item.id}</p>
                  <p className="mt-1">status: {item.status || 'unknown'}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {blocked && <p className="text-sm text-amber-200">Remove these references before archiving the credential.</p>}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="button" onClick={onConfirm} disabled={blocked} loading={loading} variant={isArchive ? 'default' : 'destructive'}>
            {isArchive ? 'Archive' : 'Confirm revoke'}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}

export default function CredentialsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const credentialsQuery = useCredentials(projectId)
  const modelsQuery = useProviderModels(projectId)
  const updateCredential = useUpdateCredential()

  const [query, setQuery] = useState('')
  const [showCredentialForm, setShowCredentialForm] = useState(false)
  const [credentialToEdit, setCredentialToEdit] = useState<ProviderCredential | null>(null)
  const [selectedCredential, setSelectedCredential] = useState<ProviderCredential | null>(null)
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const [impactLoading, setImpactLoading] = useState(false)

  const credentials = credentialsQuery.data ?? []
  const models = modelsQuery.data ?? []
  const visibleCredentialBase = useMemo(() => credentials.filter((credential) => credential.status !== 'archived'), [credentials])
  const normalizedQuery = query.trim().toLowerCase()
  const visibleCredentials = useMemo(() => {
    if (!normalizedQuery) return visibleCredentialBase
    return visibleCredentialBase.filter((credential) => `${credential.name} ${providerLabel(credential.provider)} ${String(metadataOf(credential).base_url || '')}`.toLowerCase().includes(normalizedQuery))
  }, [visibleCredentialBase, normalizedQuery])

  const modelsByCredential = useMemo(() => {
    const grouped = new Map<string, ProviderModel[]>()
    for (const model of models) {
      const current = grouped.get(model.provider_credential_id) || []
      current.push(model)
      grouped.set(model.provider_credential_id, current)
    }
    return grouped
  }, [models])

  const closeCredentialForm = () => {
    setShowCredentialForm(false)
    setCredentialToEdit(null)
  }

  const openCreateCredential = () => {
    setCredentialToEdit(null)
    setShowCredentialForm(true)
  }

  const openEditCredential = () => {
    if (!selectedCredential) return
    setCredentialToEdit(selectedCredential)
    setSelectedCredential(null)
    setShowCredentialForm(true)
  }

  const prepareAction = async (kind: 'archive' | 'revoke') => {
    if (!projectId || !selectedCredential) return
    setImpactLoading(true)
    try {
      const usage = await loadUsage(projectId)
      setConfirm({
        kind,
        credential: selectedCredential,
        usage: usageForCredential(selectedCredential, models, usage.agents, usage.releases),
      })
      setSelectedCredential(null)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to inspect credential usage')
    } finally {
      setImpactLoading(false)
    }
  }

  const confirmAction = async () => {
    if (!confirm) return
    try {
      const metadata = metadataOf(confirm.credential)
      if (confirm.kind === 'archive') {
        await updateCredential.mutateAsync({
          id: confirm.credential.id,
          data: {
            status: 'archived',
            metadata: stringMetadata({ ...metadata, archived_at: new Date().toISOString(), archive_mode: 'soft' }),
          },
        })
        toast.success('Credential archived')
      } else {
        await updateCredential.mutateAsync({
          id: confirm.credential.id,
          data: {
            status: 'revoked',
            metadata: stringMetadata({ ...metadata, revoked_at: new Date().toISOString() }),
          },
        })
        toast.success('Credential revoked')
      }
      setConfirm(null)
      await Promise.all([credentialsQuery.refetch(), modelsQuery.refetch()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Credential action failed')
    }
  }

  if (!projectId) return <ErrorState message="Project not found" />
  if (credentialsQuery.isLoading || modelsQuery.isLoading) return <LoadingState message="Loading credentials" />
  if (credentialsQuery.isError || modelsQuery.isError) return <ErrorState message="Failed to load credentials" onRetry={() => { void credentialsQuery.refetch(); void modelsQuery.refetch() }} />

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Credentials</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted">Manage provider connections shared by generation models, embedding models and agent runtime bindings in this Project.</p>
        </div>
        <Button type="button" onClick={openCreateCredential}>
          <Cable className="mr-2 h-4 w-4" />
          Connect provider
        </Button>
      </div>

      <div className="relative max-w-3xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search credentials..." className="h-11 pl-9" />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <CreateResourceCard title="Connect provider" description="Add a provider connection for models and knowledge" minHeight="sm" onClick={openCreateCredential} />

        {visibleCredentials.map((credential) => {
          const attachedModels = (modelsByCredential.get(credential.id) || []).filter((model) => !isArchived(model))
          const generationCount = attachedModels.filter((model) => !isEmbeddingModel(model)).length
          const embeddingCount = attachedModels.filter((model) => isEmbeddingModel(model)).length
          return (
            <CredentialCard
              key={credential.id}
              credential={credential}
              generationCount={generationCount}
              embeddingCount={embeddingCount}
              onClick={() => setSelectedCredential(credential)}
            />
          )
        })}

        {visibleCredentials.length === 0 && (
          <div className="flex min-h-[220px] flex-col rounded-xl border border-border/80 bg-surface/50 p-6">
            <Cable className="h-5 w-5 text-primary-light" />
            <p className="mt-5 text-base font-semibold text-white">{normalizedQuery ? 'No credentials found' : 'No provider connections yet'}</p>
            <p className="mt-2 text-sm leading-6 text-muted">{normalizedQuery ? 'Adjust the search term.' : 'Connect OpenAI, OpenRouter or an OpenAI-compatible provider.'}</p>
          </div>
        )}
      </div>

      <CredentialDetailsDialog
        credential={selectedCredential}
        attachedModels={selectedCredential ? modelsByCredential.get(selectedCredential.id) || [] : []}
        open={Boolean(selectedCredential)}
        onClose={() => setSelectedCredential(null)}
        onEdit={openEditCredential}
        onArchive={() => { void prepareAction('archive') }}
        onRevoke={() => { void prepareAction('revoke') }}
      />

      <ImpactDialog
        state={confirm}
        loading={impactLoading || updateCredential.isPending}
        onClose={() => setConfirm(null)}
        onConfirm={confirmAction}
      />

      <AddProviderCredentialModal
        open={showCredentialForm}
        onClose={closeCredentialForm}
        projectId={projectId}
        credential={credentialToEdit}
        onCredentialCreated={async () => {
          closeCredentialForm()
          await Promise.all([credentialsQuery.refetch(), modelsQuery.refetch()])
        }}
      />
    </div>
  )
}
