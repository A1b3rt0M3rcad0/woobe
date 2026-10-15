import { useMemo, useState } from 'react'
import { Key, Plus, RefreshCw } from 'lucide-react'
import { Button, Dialog, EmptyStatePanel, SectionBlock } from '@woobe/ui'
import { Select } from '@/components/ui/Select'
import type { AgentCreationFlowController } from '@/features/agents/hooks/useAgentCreationFlow'
import { providerLabel } from '@/features/agents/hooks/useAgentCreationFlow'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { ProviderConnectionConfiguration } from '@/features/provider-credentials/components/ProviderConnectionConfiguration'
import { ManualModelModal } from './ManualModelModal'
import { ModelPicker, type ModelPickerItem } from './ModelPicker'
import { ProviderConnectionModal } from './ProviderConnectionModal'

interface AgentModelStepProps { projectId: string; flow: AgentCreationFlowController }
export function credentialDisplayLabel(credential: Pick<ProviderCredential, 'name' | 'provider'>) {
  const name = credential.name.trim(), provider = providerLabel(credential.provider)
  return name.toLocaleLowerCase() === provider.toLocaleLowerCase() ? name : `${name} · ${provider}`
}
export function AgentModelStep({ projectId, flow }: AgentModelStepProps) {
  const [providerOpen, setProviderOpen] = useState(false)
  const [manualOpen, setManualOpen] = useState(false)
  const [configurationOpen, setConfigurationOpen] = useState(false)
  const [query, setQuery] = useState('')
  const existingItems = useMemo<ModelPickerItem[]>(() => {
    const search = query.trim().toLowerCase()
    return flow.usableAgentModels.filter(model => !search || `${model.name} ${model.model} ${providerLabel(model.provider)}`.toLowerCase().includes(search))
      .map(model => ({ id: model.id, title: model.name, subtitle: `${providerLabel(model.provider)} · ${model.model}` }))
  }, [flow.usableAgentModels, query])
  const catalogMatches = useMemo(() => {
    const search = query.trim().toLowerCase()
    return flow.availableModels.filter(model => !search || `${model.label} ${model.id} ${model.provider} ${model.owned_by || ''}`.toLowerCase().includes(search))
  }, [flow.availableModels, query])
  const catalogItems = catalogMatches.slice(0, 100).map(model => ({ id: model.id, title: model.label, subtitle: `${providerLabel(model.provider)} · ${model.id}`, metadata: model.context_window ? `${model.context_window.toLocaleString()} token context` : undefined }))
  const connection = flow.selectedCredential || flow.activeCredentials[0] || null
  const existing = flow.modelMode === 'existing'
  if (flow.inventoryLoading) return <EmptyStatePanel compact title="Loading Project models…" className="min-h-40" />
  if (flow.inventoryError) return <EmptyStatePanel compact title="Could not load Project models" description="Your Agent instructions are preserved. Retry to choose its model." action={<Button size="sm" variant="outline" onClick={flow.retryInventory}><RefreshCw className="h-3.5 w-3.5" />Retry</Button>} />
  return <div className="grid min-w-0 gap-4">
    {flow.usableAgentModels.length > 0 && <div className="flex flex-wrap gap-2" aria-label="Model source">
      <Button size="sm" variant={existing ? 'secondary' : 'outline'} aria-pressed={existing} onClick={() => { setQuery(''); flow.showExistingModels() }}>Project models</Button>
      <Button size="sm" variant={!existing ? 'secondary' : 'outline'} aria-pressed={!existing} onClick={() => { setQuery(''); flow.startNewModel() }}>Add model</Button>
    </div>}
    {flow.activeCredentials.length === 0 ? <EmptyStatePanel compact icon={<Key className="h-4 w-4 text-primary-light" />} title="Connect a model provider" description="Choose OpenAI, OpenRouter or another supported provider. You will save a connection, configure Draft access and then choose its model." action={<Button size="sm" onClick={() => setProviderOpen(true)}>Connect provider</Button>} /> : <>
      {!existing ? <SectionBlock title="Provider connection" actions={<Button size="sm" variant="ghost" onClick={() => setProviderOpen(true)}><Plus className="h-3.5 w-3.5" />Add connection</Button>}>
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          {flow.activeCredentials.length === 1 && connection ? <p className="min-w-0 flex-1 break-words text-sm text-foreground">{credentialDisplayLabel(connection)}</p> : <Select aria-label="Provider connection" value={flow.selectedCredential?.id || ''} onChange={event => flow.selectCredential(event.target.value)} options={flow.activeCredentials.map(item => ({ value: item.id, label: credentialDisplayLabel(item) }))} className="min-w-0 flex-1" />}
          {flow.selectedCredential && <Button size="sm" variant="outline" onClick={() => setConfigurationOpen(true)}>Configure Draft access</Button>}
        </div>
      </SectionBlock> : <p className="text-sm leading-6 text-muted-foreground">Choose a saved model. Its provider connection is already associated with it.</p>}
      {!existing && <div className="flex flex-wrap gap-2">
        {flow.canUseCatalog && flow.modelMode === 'manual' && <Button size="sm" variant="outline" onClick={() => { setQuery(''); flow.useCatalogMode() }}>Browse provider catalog</Button>}
        <Button size="sm" variant="outline" onClick={() => setManualOpen(true)}>Enter model ID manually</Button>
      </div>}
      <div className="h-[320px] min-w-0 overflow-hidden">
        {existing ? <ModelPicker items={existingItems} selectedId={flow.selectedModel?.id} query={query} onQueryChange={setQuery} onSelect={flow.selectExistingModel} emptyTitle="No matching Project models" emptyDescription="Try another search or add a model." />
          : flow.modelMode === 'catalog' ? flow.catalogError ? <EmptyStatePanel compact title="Could not load the provider catalog" description="Check the Draft API key and destination access, then retry. You can also enter a model ID manually." action={<Button size="sm" variant="outline" onClick={flow.retryCatalog}>Retry catalog</Button>} className="h-full" />
            : <ModelPicker items={catalogItems} selectedId={flow.selectedCatalogModel?.id} query={query} onQueryChange={setQuery} onSelect={id => { const model = flow.availableModels.find(item => item.id === id); if (model) flow.selectCatalogModel(model) }} loading={flow.catalogLoading} emptyTitle="No catalog models found" emptyDescription="Try another search or enter a model ID manually." resultNote={catalogMatches.length > 100 ? `Showing 100 of ${catalogMatches.length.toLocaleString()} matches. Refine your search.` : undefined} />
          : <EmptyStatePanel compact title={flow.manualModelName || flow.manualModelIdentifier || 'Enter the provider model ID'} description={flow.manualModelIdentifier || 'Use the exact identifier from your provider’s documentation.'} action={<Button size="sm" variant="outline" onClick={() => setManualOpen(true)}>{flow.manualModelIdentifier ? 'Edit model ID' : 'Enter model ID'}</Button>} className="h-full" />}
      </div>
      {!existing && <p className="text-xs leading-5 text-muted-foreground">Saving adds the model to this Project. Your Agent is created after review.</p>}
    </>}
    <ProviderConnectionModal open={providerOpen} onClose={() => setProviderOpen(false)} projectId={projectId} existingCredentials={flow.credentials} onCreated={flow.registerCreatedCredential} />
    <ManualModelModal open={manualOpen} onClose={() => setManualOpen(false)} initialIdentifier={flow.manualModelIdentifier} initialName={flow.manualModelName} onConfirm={flow.setManualModel} />
    {flow.selectedCredential && <Dialog open={configurationOpen} onClose={() => setConfigurationOpen(false)} title="Configure provider connection"><ProviderConnectionConfiguration credential={flow.selectedCredential} /><div className="mt-4 flex justify-end"><Button onClick={() => setConfigurationOpen(false)}>Done</Button></div></Dialog>}
  </div>
}
