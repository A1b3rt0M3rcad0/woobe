import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertTriangle, Cable, Cpu, Database, Pencil, RotateCcw, ShieldOff, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle, DialogFooter, SectionBlock, TechnicalListItem } from '@woobe/ui'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard, ResourcePill } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Select } from '@/components/ui/Select'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { RotateProviderCredentialDialog } from '@/features/provider-credentials/components/RotateProviderCredentialDialog'
import { useCredentials, useUpdateCredential } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { modelProviderLabel } from '@/features/provider-credentials/providers'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'
import { get } from '@/lib/api/client'

type CredentialStatusFilter = 'all' | 'active' | 'revoked'

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
  if (model.model_type) return model.model_type === 'embedding'
  if (Array.isArray(model.spec?.operations) && model.spec?.operations.includes('embedding.create')) return true
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
      items.push({ type: isEmbeddingModel(model) ? 'embedding_model' : 'generation_model', id: model.id, name: model.name, field: 'provider_credential_id', status: model.status })
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

function CredentialCard({ credential, generationCount, embeddingCount, onClick }: { credential: ProviderCredential; generationCount: number; embeddingCount: number; onClick: () => void }) {
  const baseUrl = String(metadataOf(credential).base_url || '')
  return (
    <ResourceCard
      onClick={onClick}
      aria-label={`Open provider connection ${credential.name}`}
      icon={<Cable className="h-4 w-4" />}
      title={credential.name}
      subtitle={`${modelProviderLabel(credential.provider)}${baseUrl ? ` · ${baseUrl}` : ''}`}
      status={<StatusBadge status={credential.status || 'active'} size="compact" />}
      metadata={(
        <>
          <ResourcePill tone="primary"><Cpu className="mr-1 inline h-3 w-3" />{generationCount} generation</ResourcePill>
          <ResourcePill><Database className="mr-1 inline h-3 w-3" />{embeddingCount} embedding</ResourcePill>
        </>
      )}
      footer={`Last validated · ${formatDate(credential.last_validated_at || credential.updated_at || credential.created_at)}`}
    />
  )
}

function CredentialDetailsDialog({
  credential,
  attachedModels,
  open,
  onClose,
  onEdit,
  onRotate,
  onArchive,
  onRevoke,
}: {
  credential: ProviderCredential | null
  attachedModels: ProviderModel[]
  open: boolean
  onClose: () => void
  onEdit: () => void
  onRotate: () => void
  onArchive: () => void
  onRevoke: () => void
}) {
  if (!credential) return null
  const baseUrl = String(metadataOf(credential).base_url || 'Default provider endpoint')
  const generationModels = attachedModels.filter((model) => !isEmbeddingModel(model) && !isArchived(model))
  const embeddingModels = attachedModels.filter((model) => isEmbeddingModel(model) && !isArchived(model))

  return (
    <Dialog open={open} onClose={onClose} title={credential.name}>
      <div className="grid gap-ui-md">
        <SectionBlock
          title={modelProviderLabel(credential.provider)}
          description={baseUrl}
          density="compact"
          actions={<StatusBadge status={credential.status || 'active'} size="compact" />}
        >
          <p className="font-mono text-system-meta text-muted-foreground">Created · {formatDate(credential.created_at)}</p>
        </SectionBlock>

        <SectionBlock title="Connected models" description="Models currently bound to this Project provider connection." density="compact">
          <div className="grid gap-ui-md sm:grid-cols-2">
            <div className="grid content-start gap-ui-xs">
              <p className="font-mono text-system-meta font-medium uppercase tracking-ui-label text-muted-foreground">Generation</p>
              {generationModels.length === 0 ? (
                <p className="font-sans text-product-caption text-muted-foreground">No generation models.</p>
              ) : generationModels.map((model) => (
                <TechnicalListItem key={model.id} density="compact" label={model.name} description={model.model} />
              ))}
            </div>
            <div className="grid content-start gap-ui-xs">
              <p className="font-mono text-system-meta font-medium uppercase tracking-ui-label text-muted-foreground">Embedding</p>
              {embeddingModels.length === 0 ? (
                <p className="font-sans text-product-caption text-muted-foreground">No embedding models.</p>
              ) : embeddingModels.map((model) => (
                <TechnicalListItem key={model.id} density="compact" label={model.name} description={model.model} />
              ))}
            </div>
          </div>
        </SectionBlock>

        <DialogFooter
          className="-mx-ui-panel-inset -mb-ui-panel-inset mt-ui-xs"
          meta={<span className="font-mono text-system-meta text-muted-foreground">{generationModels.length} generation · {embeddingModels.length} embedding</span>}
          actions={(
            <>
              <Button type="button" variant="outline" onClick={onEdit}><Pencil className="h-icon w-icon" />Edit</Button>
              <Button type="button" variant="outline" onClick={onRotate} disabled={credential.status !== 'active'}><RotateCcw className="h-icon w-icon" />Rotate</Button>
              <Button type="button" variant="outline" onClick={onRevoke} disabled={credential.status === 'revoked'} className="text-amber-200 hover:text-amber-100"><ShieldOff className="h-icon w-icon" />Revoke</Button>
              <Button type="button" variant="outline" onClick={onArchive} className="text-red-200 hover:text-red-100"><Trash2 className="h-icon w-icon" />Archive</Button>
            </>
          )}
        />
      </div>
    </Dialog>
  )
}

function ImpactDialog({ state, loading, onClose, onConfirm }: { state: ConfirmState; loading: boolean; onClose: () => void; onConfirm: () => void }) {
  if (!state) return null
  const isArchive = state.kind === 'archive'
  const blocked = isArchive && state.usage.length > 0

  return (
    <Dialog open={Boolean(state)} onClose={onClose} title={isArchive ? 'Archive credential' : 'Revoke credential'} className="max-w-dialog">
      <div className="grid gap-ui-md">
        <Alert variant="warning">
          <div className="flex items-start gap-ui-sm">
            <AlertTriangle className="mt-ui-hairline h-icon w-icon shrink-0" />
            <div>
              <AlertTitle>{state.credential.name}</AlertTitle>
              <AlertDescription>
                {isArchive
                  ? 'Archive is blocked while this connection is used by models, Agents or active Releases.'
                  : 'Revoking stops runtime calls that depend on this connection. Existing configuration is preserved.'}
              </AlertDescription>
            </div>
          </div>
        </Alert>

        {state.usage.length > 0 ? (
          <SectionBlock title="Current usage" description="References associated with this provider connection." density="compact">
            <div className="scrollbar-thin grid max-h-72 gap-ui-xs overflow-auto">
              {state.usage.map((item, index) => (
                <TechnicalListItem
                  key={`${item.type}-${item.id}-${item.field}-${index}`}
                  density="compact"
                  label={item.name || item.version || item.id}
                  description={`${item.type} · ${item.status || 'unknown'}`}
                  meta={item.field || undefined}
                />
              ))}
            </div>
          </SectionBlock>
        ) : null}

        {blocked ? <Alert variant="warning"><AlertDescription>Remove these references before archiving the credential.</AlertDescription></Alert> : null}

        <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-md">
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
  const [statusFilter, setStatusFilter] = useState<CredentialStatusFilter>('all')
  const [providerFilter, setProviderFilter] = useState('all')
  const [showCredentialForm, setShowCredentialForm] = useState(false)
  const [credentialToEdit, setCredentialToEdit] = useState<ProviderCredential | null>(null)
  const [credentialToRotate, setCredentialToRotate] = useState<ProviderCredential | null>(null)
  const [selectedCredential, setSelectedCredential] = useState<ProviderCredential | null>(null)
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const [impactLoading, setImpactLoading] = useState(false)

  const credentials = credentialsQuery.data ?? []
  const models = modelsQuery.data ?? []
  const visibleCredentialBase = useMemo(() => credentials.filter((credential) => credential.status !== 'archived'), [credentials])
  const statusCounts = useMemo(() => ({
    all: visibleCredentialBase.length,
    active: visibleCredentialBase.filter((credential) => !credential.status || credential.status.toLowerCase() === 'active').length,
    revoked: visibleCredentialBase.filter((credential) => credential.status?.toLowerCase() === 'revoked').length,
  }), [visibleCredentialBase])
  const providerOptions = useMemo(() => Array.from(new Set(visibleCredentialBase.map((credential) => credential.provider).filter(Boolean))).sort(), [visibleCredentialBase])
  const normalizedQuery = query.trim().toLowerCase()
  const visibleCredentials = useMemo(() => visibleCredentialBase.filter((credential) => {
    const normalizedStatus = credential.status?.toLowerCase() || 'active'
    const matchesStatus = statusFilter === 'all' || normalizedStatus === statusFilter
    const matchesProvider = providerFilter === 'all' || credential.provider === providerFilter
    const matchesQuery = !normalizedQuery || `${credential.name} ${modelProviderLabel(credential.provider)} ${String(metadataOf(credential).base_url || '')}`.toLowerCase().includes(normalizedQuery)
    return matchesStatus && matchesProvider && matchesQuery
  }), [visibleCredentialBase, normalizedQuery, providerFilter, statusFilter])

  const modelsByCredential = useMemo(() => {
    const grouped = new Map<string, ProviderModel[]>()
    for (const model of models) {
      const current = grouped.get(model.provider_credential_id) || []
      current.push(model)
      grouped.set(model.provider_credential_id, current)
    }
    return grouped
  }, [models])

  const rotatingModels = credentialToRotate ? (modelsByCredential.get(credentialToRotate.id) || []).filter((model) => !isArchived(model)) : []
  const rotatingGenerationCount = rotatingModels.filter((model) => !isEmbeddingModel(model)).length
  const rotatingEmbeddingCount = rotatingModels.filter((model) => isEmbeddingModel(model)).length

  const closeCredentialForm = () => { setShowCredentialForm(false); setCredentialToEdit(null) }
  const openCreateCredential = () => { setCredentialToEdit(null); setShowCredentialForm(true) }
  const openEditCredential = () => { if (!selectedCredential) return; setCredentialToEdit(selectedCredential); setSelectedCredential(null); setShowCredentialForm(true) }
  const openRotateCredential = () => { if (!selectedCredential || selectedCredential.status !== 'active') return; setCredentialToRotate(selectedCredential); setSelectedCredential(null) }
  const closeRotateCredential = () => { if (credentialToRotate) setSelectedCredential(credentialToRotate); setCredentialToRotate(null) }

  const prepareAction = async (kind: 'archive' | 'revoke') => {
    if (!projectId || !selectedCredential) return
    setImpactLoading(true)
    try {
      const usage = await loadUsage(projectId)
      setConfirm({ kind, credential: selectedCredential, usage: usageForCredential(selectedCredential, models, usage.agents, usage.releases) })
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
        await updateCredential.mutateAsync({ id: confirm.credential.id, data: { status: 'archived', metadata: stringMetadata({ ...metadata, archived_at: new Date().toISOString(), archive_mode: 'soft' }) } })
        toast.success('Credential archived')
      } else {
        await updateCredential.mutateAsync({ id: confirm.credential.id, data: { status: 'revoked', metadata: stringMetadata({ ...metadata, revoked_at: new Date().toISOString() }) } })
        toast.success('Credential revoked')
      }
      setConfirm(null)
      await Promise.all([credentialsQuery.refetch(), modelsQuery.refetch()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Credential action failed')
    }
  }

  if (!projectId) return <ErrorState message="Project not found" />
  const isLoading = credentialsQuery.isLoading || modelsQuery.isLoading
  const isError = credentialsQuery.isError || modelsQuery.isError
  const hasFilters = Boolean(normalizedQuery) || statusFilter !== 'all' || providerFilter !== 'all'
  const resultCount = hasFilters ? `${visibleCredentials.length} of ${visibleCredentialBase.length}` : visibleCredentialBase.length

  return (
    <ResourcePage title="Credentials" description="Manage provider connections shared by Models, Knowledge and Agent runtime bindings." action={<Button type="button" onClick={openCreateCredential}><Cable className="mr-2 h-4 w-4" />Connect Provider</Button>}>
      <ResourceToolbar>
        <ResourceTabs
          value={statusFilter}
          onChange={setStatusFilter}
          label="Filter Credentials by status"
          tabs={[
            { value: 'all', label: 'All', count: statusCounts.all },
            { value: 'active', label: 'Active', count: statusCounts.active },
            { value: 'revoked', label: 'Revoked', count: statusCounts.revoked },
          ]}
        />
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px]">
          <ResourceSearch value={query} onChange={setQuery} placeholder="Search Credentials, providers or endpoints..." label="Search Credentials" />
          <Select value={providerFilter} onChange={(event) => setProviderFilter(event.target.value)} className="h-10" options={[{ value: 'all', label: 'All providers' }, ...providerOptions.map((provider) => ({ value: provider, label: modelProviderLabel(provider) }))]} />
        </div>
      </ResourceToolbar>

      <section>
        <ResourceSectionHeader title="Provider connections" description="Open a connection to inspect Models, rotate its key or manage lifecycle." count={resultCount} />
        {isLoading ? (
          <LoadingState message="Loading Credentials" variant="panel" layout="compact-cards" />
        ) : isError ? (
          <ErrorState message="Failed to load Credentials" onRetry={() => { void credentialsQuery.refetch(); void modelsQuery.refetch() }} className="rounded-xl border border-border/80 bg-surface/40 py-10" />
        ) : visibleCredentials.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visibleCredentials.map((credential) => {
              const attachedModels = (modelsByCredential.get(credential.id) || []).filter((model) => !isArchived(model))
              const generationCount = attachedModels.filter((model) => !isEmbeddingModel(model)).length
              const embeddingCount = attachedModels.filter((model) => isEmbeddingModel(model)).length
              return <CredentialCard key={credential.id} credential={credential} generationCount={generationCount} embeddingCount={embeddingCount} onClick={() => setSelectedCredential(credential)} />
            })}
          </div>
        ) : (
          <ResourceEmptyState
            icon={<Cable className="h-4 w-4" />}
            title={visibleCredentialBase.length === 0 ? 'No Provider connections yet' : 'No Credentials found'}
            description={visibleCredentialBase.length === 0 ? 'Connect OpenAI, OpenRouter or an OpenAI-compatible provider.' : 'Adjust the search or clear the active filters.'}
            action={hasFilters ? <Button type="button" size="sm" variant="outline" onClick={() => { setQuery(''); setStatusFilter('all'); setProviderFilter('all') }}>Clear filters</Button> : undefined}
          />
        )}
      </section>

      <CredentialDetailsDialog
        credential={selectedCredential}
        attachedModels={selectedCredential ? modelsByCredential.get(selectedCredential.id) || [] : []}
        open={Boolean(selectedCredential)}
        onClose={() => setSelectedCredential(null)}
        onEdit={openEditCredential}
        onRotate={openRotateCredential}
        onArchive={() => { void prepareAction('archive') }}
        onRevoke={() => { void prepareAction('revoke') }}
      />

      <RotateProviderCredentialDialog
        open={Boolean(credentialToRotate)}
        credential={credentialToRotate}
        projectId={projectId}
        generationCount={rotatingGenerationCount}
        embeddingCount={rotatingEmbeddingCount}
        onClose={closeRotateCredential}
        onRotated={async (rotated) => {
          setCredentialToRotate(null)
          setSelectedCredential(rotated)
          await Promise.all([credentialsQuery.refetch(), modelsQuery.refetch()])
        }}
      />

      <ImpactDialog state={confirm} loading={impactLoading || updateCredential.isPending} onClose={() => setConfirm(null)} onConfirm={confirmAction} />

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
    </ResourcePage>
  )
}
