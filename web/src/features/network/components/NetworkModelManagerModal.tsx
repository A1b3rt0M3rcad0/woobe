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

export function NetworkModelManagerModal({ open, projectId, selectedModelId, onClose, onUseModel }: Props) {
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
      pricing: {
        input_cost_per_1m_tokens: inputCost.trim() ? Number(inputCost) : null,
        output_cost_per_1m_tokens: outputCost.trim() ? Number(outputCost) : null,
        currency: currency.trim().toUpperCase() || 'USD',
        billing_unit: 'per_1m_tokens',
      },
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
    <Dialog open={open} onClose={onClose} title="Manage models" className="max-w-4xl overflow-hidden bg-surface/95">
      <div className="-m-6 flex max-h-[76vh] min-h-[560px] flex-col overflow-hidden">
        {screen === 'list' ? <>
          <div className="flex shrink-0 gap-3 border-b border-border/80 p-4">
            <div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models..." className="pl-9" /></div>
            <Button size="sm" variant="outline" onClick={() => openConnection()}><KeyRound className="mr-2 h-3.5 w-3.5" />Connect</Button>
            <Button size="sm" onClick={() => openModel()}><Plus className="mr-2 h-3.5 w-3.5" />New model</Button>
          </div>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-4">
            {filtered.length === 0 ? <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted">No models configured.</div> : <div className="grid gap-3 sm:grid-cols-2">{filtered.map((model) => {
              const credential = credentials.find((item) => item.id === model.provider_credential_id)
              const selected = model.id === selectedModelId
              return <article key={model.id} className={cn('rounded-xl border p-4', selected ? 'border-primary/40 bg-primary/[0.05]' : 'border-border/80 bg-background/50')}>
                <div className="flex gap-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface"><Cpu className="h-4 w-4 text-primary-light" /></div><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate text-sm font-medium text-white">{model.name}</p>{selected ? <Check className="h-3.5 w-3.5 text-primary-light" /> : null}</div><p className="mt-1 truncate font-mono text-xs text-muted">{model.model}</p><p className="mt-2 truncate text-[11px] text-muted">{providerLabel(model.provider || credential?.provider)} · {credential?.name || 'Missing connection'}</p></div></div>
                <div className="mt-3 flex justify-end gap-2 border-t border-border/70 pt-3"><Button size="sm" variant="ghost" onClick={() => openModel(model)}><Pencil className="mr-1 h-3.5 w-3.5" />Edit</Button><Button size="sm" onClick={() => { onUseModel(model, credential); onClose() }}>Use model</Button></div>
              </article>
            })}</div>}
          </div>
        </> : screen === 'credential' ? <>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5"><div className="mx-auto max-w-xl space-y-4"><p className="text-sm font-medium text-white">{editingCredential ? 'Edit provider connection' : 'Connect provider'}</p><label className="block text-xs font-medium text-muted">Provider<Select className="mt-1.5" value={provider} onChange={(event) => setProvider(event.target.value)} options={providerOptions} /></label><label className="block text-xs font-medium text-muted">Connection name<Input className="mt-1.5" value={connectionName} onChange={(event) => setConnectionName(event.target.value)} /></label>{provider === 'custom' ? <label className="block text-xs font-medium text-muted">Base URL<Input className="mt-1.5" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} /></label> : null}<label className="block text-xs font-medium text-muted">{editingCredential ? 'Replace API key (optional)' : 'API key'}<Input type="password" className="mt-1.5" value={secret} onChange={(event) => setSecret(event.target.value)} /></label></div></div>
          <div className="flex shrink-0 justify-end gap-2 border-t border-border/80 p-4"><Button variant="outline" onClick={() => setScreen(editingModel || credentialId ? 'model' : 'list')}>Cancel</Button><Button onClick={() => void saveConnection()} loading={createCredential.isPending || updateCredential.isPending}>Save connection</Button></div>
        </> : <>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5"><div className="mx-auto max-w-2xl space-y-4">
            <p className="text-sm font-medium text-white">{editingModel ? 'Edit model' : 'Create model'}</p>
            <div className="flex items-end gap-2"><label className="min-w-0 flex-1 text-xs font-medium text-muted">Provider connection<Select className="mt-1.5" value={credentialId} onChange={(event) => { setCredentialId(event.target.value); setCatalogId('') }} options={[{ value: '', label: 'Select a connection' }, ...credentials.filter((item) => item.status !== 'inactive').map((item) => ({ value: item.id, label: `${item.name} · ${providerLabel(item.provider)}` }))]} /></label><Button size="sm" variant="outline" onClick={() => openConnection(selectedCredential)}>{selectedCredential ? 'Edit connection' : 'Connect'}</Button></div>
            {!editingModel && credentialId && (catalogQuery.data?.length || 0) > 0 ? <label className="block text-xs font-medium text-muted">Provider catalog<Select className="mt-1.5" value={catalogId} onChange={(event) => { const item = catalogQuery.data?.find((model) => model.id === event.target.value); setCatalogId(event.target.value); if (item) { setModelId(item.id); setDisplayName(item.label) } }} options={[{ value: '', label: 'Enter model manually' }, ...(catalogQuery.data ?? []).slice(0, 100).map((item) => ({ value: item.id, label: `${item.label} · ${item.id}` }))]} /></label> : null}
            <div className="grid gap-4 sm:grid-cols-2"><label className="text-xs font-medium text-muted">Display name<Input className="mt-1.5" value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label><label className="text-xs font-medium text-muted">Model ID<Input className="mt-1.5 font-mono" value={modelId} onChange={(event) => setModelId(event.target.value)} /></label><label className="text-xs font-medium text-muted">Input / 1M<Input type="number" min="0" step="0.000001" className="mt-1.5" value={inputCost} onChange={(event) => setInputCost(event.target.value)} /></label><label className="text-xs font-medium text-muted">Output / 1M<Input type="number" min="0" step="0.000001" className="mt-1.5" value={outputCost} onChange={(event) => setOutputCost(event.target.value)} /></label><label className="text-xs font-medium text-muted">Currency<Input className="mt-1.5 uppercase" maxLength={3} value={currency} onChange={(event) => setCurrency(event.target.value)} /></label>{editingModel ? <label className="text-xs font-medium text-muted">Status<Select className="mt-1.5" value={status} onChange={(event) => setStatus(event.target.value)} options={[{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }, { value: 'archived', label: 'Archived' }]} /></label> : null}</div>
          </div></div>
          <div className="flex shrink-0 justify-end gap-2 border-t border-border/80 p-4"><Button variant="outline" onClick={() => setScreen('list')} disabled={busy}>Cancel</Button><Button onClick={() => void saveModel()} loading={createModel.isPending || updateModel.isPending}>{editingModel ? 'Save and use' : 'Create and use'}</Button></div>
        </>}
      </div>
    </Dialog>
  )
}
