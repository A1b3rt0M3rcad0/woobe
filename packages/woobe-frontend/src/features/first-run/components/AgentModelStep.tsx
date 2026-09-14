import { useMemo, useState } from 'react'
import { CheckCircle2, Key, Plus, RefreshCw } from 'lucide-react'
import { EmptyStatePanel, SectionBlock } from '@woobe/ui'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import type { AgentCreationFlowController } from '@/features/agents/hooks/useAgentCreationFlow'
import { providerLabel } from '@/features/agents/hooks/useAgentCreationFlow'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { ManualModelModal } from './ManualModelModal'
import { ModelPicker, type ModelPickerItem } from './ModelPicker'
import { ProviderConnectionModal } from './ProviderConnectionModal'

interface AgentModelStepProps { projectId: string; flow: AgentCreationFlowController }

export function credentialDisplayLabel(credential: Pick<ProviderCredential, 'name' | 'provider'>) {
  const name = credential.name.trim()
  const provider = providerLabel(credential.provider)
  return name.toLocaleLowerCase() === provider.toLocaleLowerCase() ? name : `${name} · ${provider}`
}

export function AgentModelStep({ projectId, flow }: AgentModelStepProps) {
  const [providerModalOpen, setProviderModalOpen] = useState(false)
  const [manualModalOpen, setManualModalOpen] = useState(false)
  const [query, setQuery] = useState('')

  const existingItems = useMemo<ModelPickerItem[]>(() => {
    const normalized = query.trim().toLowerCase()
    return flow.usableAgentModels.filter((model) => !normalized || `${model.name} ${model.model} ${providerLabel(model.provider)}`.toLowerCase().includes(normalized)).map((model) => ({ id: model.id, title: model.name, subtitle: `${providerLabel(model.provider)} · ${model.model}` }))
  }, [flow.usableAgentModels, query])

  const catalogMatches = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return flow.availableModels.filter((model) => !normalized || `${model.label} ${model.id} ${model.provider} ${model.owned_by || ''}`.toLowerCase().includes(normalized))
  }, [flow.availableModels, query])

  const catalogItems = useMemo<ModelPickerItem[]>(() => catalogMatches.slice(0, 100).map((model) => ({ id: model.id, title: model.label, subtitle: `${providerLabel(model.provider)} · ${model.id}`, metadata: model.context_window ? `${model.context_window.toLocaleString()} token context` : undefined })), [catalogMatches])

  if (flow.inventoryLoading) return <EmptyStatePanel compact title="Loading Project model inventory..." className="h-full min-h-40" />
  if (flow.inventoryError) return <EmptyStatePanel compact title="Could not load the Project model inventory" description="Retry before selecting the model used by this Agent." action={<Button type="button" size="sm" variant="outline" onClick={flow.retryInventory}><RefreshCw className="mr-1.5 h-3.5 w-3.5" />Retry</Button>} className="h-full min-h-40" />

  const openNewModel = () => { setQuery(''); flow.startNewModel() }
  const openExistingModels = () => { setQuery(''); flow.showExistingModels() }
  const selectCatalogModel = (modelId: string) => { const model = flow.availableModels.find((item) => item.id === modelId); if (model) flow.selectCatalogModel(model) }
  const selectedConnection = flow.selectedCredential || flow.activeCredentials[0] || null
  const catalogResultNote = catalogMatches.length > 100 ? `Showing the first 100 of ${catalogMatches.length.toLocaleString()} matching models. Refine the search to narrow the list.` : undefined

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_auto_minmax(0,1fr)] gap-3 overflow-hidden">
      {flow.activeCredentials.length === 0 ? (
        <EmptyStatePanel compact icon={<Key className="h-4 w-4 text-primary-light" />} title="No provider connection" description="Connect OpenAI, OpenRouter or another OpenAI-compatible provider before selecting the Agent model." action={<Button type="button" size="sm" onClick={() => setProviderModalOpen(true)}>Connect provider</Button>} />
      ) : (
        <SectionBlock density="compact" title="Provider connection" actions={<Button type="button" size="sm" variant="ghost" onClick={() => setProviderModalOpen(true)}><Plus className="mr-1 h-3.5 w-3.5" />Add connection</Button>}>
          <div className="flex min-w-0 items-center gap-2.5"><CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />{flow.activeCredentials.length === 1 && selectedConnection ? <p className="truncate font-mono text-[10px] text-slate-200" title={credentialDisplayLabel(selectedConnection)}>{credentialDisplayLabel(selectedConnection)}</p> : <Select value={flow.selectedCredential?.id || ''} onChange={(event) => flow.selectCredential(event.target.value)} options={flow.activeCredentials.map((credential) => ({ value: credential.id, label: credentialDisplayLabel(credential) }))} className="min-w-64" />}</div>
        </SectionBlock>
      )}

      {flow.activeCredentials.length > 0 ? <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2"><div className="flex items-center gap-1.5">{flow.usableAgentModels.length > 0 ? <Button type="button" size="sm" variant={flow.modelMode === 'existing' ? 'secondary' : 'outline'} onClick={openExistingModels}>Existing models</Button> : null}<Button type="button" size="sm" variant={flow.modelMode !== 'existing' ? 'secondary' : 'outline'} onClick={openNewModel}>Add new model</Button></div>{flow.modelMode !== 'existing' ? <div className="flex items-center gap-1.5">{flow.canUseCatalog && flow.modelMode === 'manual' ? <Button type="button" size="sm" variant="ghost" onClick={() => { setQuery(''); flow.useCatalogMode() }}>Browse provider catalog</Button> : null}<Button type="button" size="sm" variant="ghost" onClick={() => setManualModalOpen(true)}>Enter model ID manually</Button></div> : null}</div> : null}

      {flow.activeCredentials.length > 0 ? <div className="h-full min-h-0 overflow-hidden">{flow.modelMode === 'existing' ? <ModelPicker items={existingItems} selectedId={flow.selectedModel?.id} query={query} onQueryChange={setQuery} onSelect={flow.selectExistingModel} emptyTitle="No active generation models" emptyDescription="Add a new model using one of the Project provider connections." /> : flow.modelMode === 'catalog' ? flow.catalogError ? <EmptyStatePanel compact title="Could not load the provider catalog" description="Retry discovery or enter the model identifier manually." action={<div className="flex gap-2"><Button type="button" size="sm" variant="outline" onClick={flow.retryCatalog}>Retry</Button><Button type="button" size="sm" variant="ghost" onClick={() => setManualModalOpen(true)}>Enter model ID</Button></div>} className="h-full" /> : <ModelPicker items={catalogItems} selectedId={flow.selectedCatalogModel?.id} query={query} onQueryChange={setQuery} onSelect={selectCatalogModel} loading={flow.catalogLoading} emptyTitle="No catalog models found" emptyDescription="Try another search or enter the model identifier manually." resultNote={catalogResultNote} /> : <EmptyStatePanel compact title={flow.manualModelIdentifier ? (flow.manualModelName || flow.manualModelIdentifier) : 'Enter the provider model ID'} description={flow.manualModelIdentifier || 'This provider does not expose a compatible model catalog, or the model is not listed.'} action={<Button type="button" size="sm" variant="outline" onClick={() => setManualModalOpen(true)}>{flow.manualModelIdentifier ? 'Edit model ID' : 'Enter model ID'}</Button>} className="h-full" />}</div> : null}

      <ProviderConnectionModal open={providerModalOpen} onClose={() => setProviderModalOpen(false)} projectId={projectId} existingCredentials={flow.credentials} onCreated={flow.registerCreatedCredential} />
      <ManualModelModal open={manualModalOpen} onClose={() => setManualModalOpen(false)} initialIdentifier={flow.manualModelIdentifier} initialName={flow.manualModelName} onConfirm={flow.setManualModel} />
    </div>
  )
}
