import { useEffect, useMemo, useState } from 'react'
import { Check, Cpu, KeyRound, Pencil, Plus, Search } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { useCreateCredential, useCredentials, useUpdateCredential } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { useAvailableProviderModels, useCreateProviderModel, useProviderModels, useUpdateProviderModel } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'
import { cn } from '@/lib/utils'

type Screen = 'list' | 'model' | 'credential'

interface Props {
  open: boolean
  projectId: string
  selectedModelId: string | null
  onClose: () => void
  onUseModel: (model: ProviderModel, credential?: ProviderCredential | null) => void
}

const providerOptions = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'custom', label: 'OpenAI Compatible' },
]

function providerLabel(value?: string | null) {
  return value === 'openai' ? 'OpenAI' : value === 'openrouter' ? 'OpenRouter' : value === 'custom' ? 'OpenAI Compatible' : value || 'Unknown'
}

function credentialMetadata(provider: string, baseUrl: string): Record<string, string> {
  if (provider === 'openrouter') return { provider_family: 'openrouter', compatibility: 'native', base_url: 'https://openrouter.ai/api/v1', model_discovery_strategy: 'openrouter_models' }
  if (provider === 'custom') return { provider_family: 'openai', compatibility: 'compatible', base_url: baseUrl.trim(), model_discovery_strategy: 'openai_compatible_models' }
  return { provider_family: 'openai', compatibility: 'native', model_discovery_strategy: 'openai_models' }
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <span className="mb-1.5 block font-mono text-[8px] font-medium uppercase tracking-[0.1em] text-muted-foreground">{children}</span>
}

function FormHeader({ title, description }: { title: string; description: string }) {
  return <div className="border-b border-border pb-3"><h3 className="font-mono text-[10px] font-bold text-slate-50">{title}</h3><p className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">{description}</p></div>
}

export function AgentModelManagerModal({ open, projectId, selectedModelId, onClose, onUseModel }: Props) {
  const credentialsQuery = useCredentials(projectId)
  const modelsQuery = useProviderModels(projectId)
  const createCredential = useCreateCredential()
  const updateCredential = useUpdateCredential()
  const createModel = useCreateProviderModel()
  const updateModel = useUpdateProviderModel()
  const credentials = credentialsQuery.data ?? []
  const models = modelsQuery.data ?? []

  const [screen, setScreen] = useState<Screen>('list')
  const [query, setQuery] = useState('')
  const [editingModel, setEditingModel] = useState<ProviderModel | null>(null)
  const [credentialId, setCredentialId] = useState('')
  const [modelId, setModelId] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [status, setStatus] = useState('active')
  const [inputCost, setInputCost] = useState('')
  const [outputCost, setOutputCost] = useState('')
  const [currency, setCurrency] = useState('USD')
  const [catalogId, setCatalogId] = useState('')
  const [editingCredential, setEditingCredential] = useState<ProviderCredential | null>(null)
  const [provider, setProvider] = useState('openai')
  const [connectionName, setConnectionName] = useState('')
  const [secret, setSecret] = useState('')
  const [baseUrl, setBaseUrl] = useState('')

  const catalogQuery = useAvailableProviderModels(projectId, screen === 'model' && credentialId && !editingModel ? credentialId : undefined, 'generation')
  const selectedCredential = credentials.find((item) => item.id === credentialId) || null
  const selectedCatalog = (catalogQuery.data ?? []).find((item) => item.id === catalogId) || null
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return models.filter((model) => model.status !== 'archived' && (!normalized || `${model.name} ${model.model} ${model.provider || ''}`.toLowerCase().includes(normalized)))
  }, [models, query])

  useEffect(() => {
    if (!open) return
    setScreen('list')
    setQuery('')
    setEditingModel(null)
  }, [open])

  const openModel = (model?: ProviderModel) => {
    const pricing = (model?.metadata?.pricing || {}) as Record<string, unknown>
    setEditingModel(model || null)
    setCredentialId(model?.provider_credential_id || credentials.find((item) => item.status !== 'inactive')?.id || '')
    setModelId(model?.model || '')
    setDisplayName(model?.name || '')
    setStatus(model?.status || 'active')
    setInputCost(pricing.input_cost_per_1m_tokens == null ? '' : String(pricing.input_cost_per_1m_tokens))
    setOutputCost(pricing.output_cost_per_1m_tokens == null ? '' : String(pricing.output_cost_per_1m_tokens))
    setCurrency(typeof pricing.currency === 'string' ? pricing.currency : 'USD')
    setCatalogId('')
    setScreen('model')
  }

  const openConnection = (credential?: ProviderCredential | null) => {
    setEditingCredential(credential || null)
    setProvider(credential?.provider || 'openai')
    setConnectionName(credential?.name || '')
    setSecret('')
    setBaseUrl(String(credential?.metadata?.base_url || ''))
    setScreen('credential')
  }

  const saveConnection = async () => {
    if (!connectionName.trim()) return toast.error('Connection name is required')
    if (!editingCredential && !secret.trim()) return toast.error('API key is required')
    if (provider === 'custom' && !baseUrl.trim()) return toast.error('Base URL is required')
    try {
      if (editingCredential) {
        await updateCredential.mutateAsync({ id: editingCredential.id, data: { name: connectionName.trim(), provider, ...(secret.trim() ? { secret: secret.trim() } : {}), metadata: credentialMetadata(provider, baseUrl) } })
        setCredentialId(editingCredential.id)
      } else {
        const created = await createCredential.mutateAsync({ project_id: projectId, provider, name: connectionName.trim(), secret: secret.trim(), metadata: credentialMetadata(provider, baseUrl) })
        setCredentialId(created.id)
      }
      await credentialsQuery.refetch()
      toast.success('Provider connection saved')
      setScreen('model')
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to save connection') }
  }

  const saveModel = async () => {
    const resolvedId = (selectedCatalog?.id || modelId).trim()
    const resolvedName = (selectedCatalog?.label || displayName || resolvedId).trim()
    if (!credentialId) return toast.error('Choose a provider connection')
    if (!resolvedId || !resolvedName) return toast.error('Model name and ID are required')
    const metadata = {
      ...(editingModel?.metadata || {}),
      capability: 'generation',
      source: selectedCatalog ? 'remote' : 'manual',
      pricing: { input_cost_per_1m_tokens: inputCost.trim() ? Number(inputCost) : null, output_cost_per_1m_tokens: outputCost.trim() ? Number(outputCost) : null, currency: currency.trim().toUpperCase() || 'USD', billing_unit: 'per_1m_tokens' },
    }
    try {
      const saved = editingModel
        ? await updateModel.mutateAsync({ id: editingModel.id, data: { provider_credential_id: credentialId, name: resolvedName, model: resolvedId, status, metadata } })
        : await createModel.mutateAsync({ project_id: projectId, provider_credential_id: credentialId, name: resolvedName, model: resolvedId, metadata })
      await modelsQuery.refetch()
      onUseModel(saved, credentials.find((item) => item.id === credentialId) || selectedCredential)
      toast.success(editingModel ? 'Model updated and selected' : 'Model created and selected')
      onClose()
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to save model') }
  }

  const busy = createCredential.isPending || updateCredential.isPending || createModel.isPending || updateModel.isPending

  return (
    <Dialog open={open} onClose={onClose} title="Manage models" className="flex h-[min(720px,calc(100svh-2rem))] max-w-4xl flex-col overflow-hidden" contentClassName="min-h-0 flex-1 p-0">
      <div className="flex h-full min-h-0 flex-col">
        {screen === 'list' ? <>
          <div className="flex shrink-0 gap-2 border-b border-border bg-background/15 p-3">
            <div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models..." className="pl-9" /></div>
            <Button size="sm" variant="outline" onClick={() => openConnection()}><KeyRound className="h-3.5 w-3.5" />Connect</Button>
            <Button size="sm" onClick={() => openModel()}><Plus className="h-3.5 w-3.5" />New model</Button>
          </div>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-3">
            {filtered.length === 0 ? <div className="rounded-container border border-dashed border-border bg-background/20 px-4 py-8 text-center font-sans text-[10px] text-muted-foreground">No models configured.</div> : <div className="divide-y divide-border/60 rounded-container border border-border bg-background/20">{filtered.map((model) => {
              const credential = credentials.find((item) => item.id === model.provider_credential_id)
              const selected = model.id === selectedModelId
              return <article key={model.id} className={cn('grid gap-3 px-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center', selected && 'bg-primary/[0.045]')}>
                <div className="flex min-w-0 gap-2.5"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><Cpu className="h-3.5 w-3.5" /></span><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate font-mono text-[9px] font-semibold text-slate-100">{model.name}</p>{selected ? <Check className="h-3 w-3 text-primary-light" /> : null}</div><p className="mt-1 truncate font-mono text-[8px] text-muted-foreground">{model.model}</p><p className="mt-1 font-sans text-[9px] text-muted-foreground">{providerLabel(model.provider || credential?.provider)} · {credential?.name || 'Missing connection'}</p></div></div>
                <div className="flex justify-end gap-2"><Button size="sm" variant="ghost" onClick={() => openModel(model)}><Pencil className="h-3.5 w-3.5" />Edit</Button><Button size="sm" onClick={() => { onUseModel(model, credential); onClose() }}>Use model</Button></div>
              </article>
            })}</div>}
          </div>
        </> : screen === 'credential' ? <>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5"><div className="mx-auto max-w-xl space-y-4"><FormHeader title={editingCredential ? 'Edit provider connection' : 'Connect provider'} description="Store provider credentials separately from the Agent Draft." /><label className="block"><FieldLabel>Provider</FieldLabel><Select value={provider} onChange={(event) => setProvider(event.target.value)} options={providerOptions} /></label><label className="block"><FieldLabel>Connection name</FieldLabel><Input value={connectionName} onChange={(event) => setConnectionName(event.target.value)} /></label>{provider === 'custom' ? <label className="block"><FieldLabel>Base URL</FieldLabel><Input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} /></label> : null}<label className="block"><FieldLabel>{editingCredential ? 'Replace API key (optional)' : 'API key'}</FieldLabel><Input type="password" value={secret} onChange={(event) => setSecret(event.target.value)} /></label></div></div>
          <div className="flex min-h-[56px] shrink-0 justify-end gap-2 border-t border-border bg-surface/[0.98] px-4 py-3"><Button variant="outline" onClick={() => setScreen(editingModel || credentialId ? 'model' : 'list')}>Cancel</Button><Button onClick={() => void saveConnection()} loading={createCredential.isPending || updateCredential.isPending}>Save connection</Button></div>
        </> : <>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5"><div className="mx-auto max-w-2xl space-y-4">
            <FormHeader title={editingModel ? 'Edit model' : 'Create model'} description="Bind a generation model to one provider connection and optional pricing metadata." />
            <div className="flex items-end gap-2"><label className="min-w-0 flex-1"><FieldLabel>Provider connection</FieldLabel><Select value={credentialId} onChange={(event) => { setCredentialId(event.target.value); setCatalogId('') }} options={[{ value: '', label: 'Select a connection' }, ...credentials.filter((item) => item.status !== 'inactive').map((item) => ({ value: item.id, label: `${item.name} · ${providerLabel(item.provider)}` }))]} /></label><Button size="sm" variant="outline" onClick={() => openConnection(selectedCredential)}>{selectedCredential ? 'Edit connection' : 'Connect'}</Button></div>
            {!editingModel && credentialId && (catalogQuery.data?.length || 0) > 0 ? <label className="block"><FieldLabel>Provider catalog</FieldLabel><Select value={catalogId} onChange={(event) => { const item = catalogQuery.data?.find((model) => model.id === event.target.value); setCatalogId(event.target.value); if (item) { setModelId(item.id); setDisplayName(item.label) } }} options={[{ value: '', label: 'Enter model manually' }, ...(catalogQuery.data ?? []).slice(0, 100).map((item) => ({ value: item.id, label: `${item.label} · ${item.id}` }))]} /></label> : null}
            <div className="grid gap-4 sm:grid-cols-2"><label><FieldLabel>Display name</FieldLabel><Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label><label><FieldLabel>Model ID</FieldLabel><Input className="font-mono" value={modelId} onChange={(event) => setModelId(event.target.value)} /></label><label><FieldLabel>Input / 1M</FieldLabel><Input type="number" min="0" step="0.000001" value={inputCost} onChange={(event) => setInputCost(event.target.value)} /></label><label><FieldLabel>Output / 1M</FieldLabel><Input type="number" min="0" step="0.000001" value={outputCost} onChange={(event) => setOutputCost(event.target.value)} /></label><label><FieldLabel>Currency</FieldLabel><Input className="uppercase" maxLength={3} value={currency} onChange={(event) => setCurrency(event.target.value)} /></label>{editingModel ? <label><FieldLabel>Status</FieldLabel><Select value={status} onChange={(event) => setStatus(event.target.value)} options={[{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }, { value: 'archived', label: 'Archived' }]} /></label> : null}</div>
          </div></div>
          <div className="flex min-h-[56px] shrink-0 justify-end gap-2 border-t border-border bg-surface/[0.98] px-4 py-3"><Button variant="outline" onClick={() => setScreen('list')} disabled={busy}>Cancel</Button><Button onClick={() => void saveModel()} loading={createModel.isPending || updateModel.isPending}>{editingModel ? 'Save and use' : 'Create and use'}</Button></div>
        </>}
      </div>
    </Dialog>
  )
}
