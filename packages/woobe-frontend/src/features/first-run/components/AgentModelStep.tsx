import { useMemo, useState } from 'react'
import { CheckCircle2, Key, Plus, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import type { AgentCreationFlowController } from '@/features/agents/hooks/useAgentCreationFlow'
import { providerLabel } from '@/features/agents/hooks/useAgentCreationFlow'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { ManualModelModal } from './ManualModelModal'
import { ModelPicker, type ModelPickerItem } from './ModelPicker'
import { ProviderConnectionModal } from './ProviderConnectionModal'

interface AgentModelStepProps {
  projectId: string
  flow: AgentCreationFlowController
}

export function credentialDisplayLabel(credential: Pick<ProviderCredential, 'name' | 'provider'>) {
  const name = credential.name.trim()
  const provider = providerLabel(credential.provider)
  return name.toLocaleLowerCase() === provider.toLocaleLowerCase()
    ? name
    : `${name} · ${provider}`
}

export function AgentModelStep({ projectId, flow }: AgentModelStepProps) {
  const [providerModalOpen, setProviderModalOpen] = useState(false)
  const [manualModalOpen, setManualModalOpen] = useState(false)
  const [query, setQuery] = useState('')

  const existingItems = useMemo<ModelPickerItem[]>(() => {
    const normalized = query.trim().toLowerCase()
    return flow.usableAgentModels
      .filter((model) => !normalized || `${model.name} ${model.model} ${providerLabel(model.provider)}`.toLowerCase().includes(normalized))
      .map((model) => ({
        id: model.id,
        title: model.name,
        subtitle: `${providerLabel(model.provider)} · ${model.model}`,
      }))
  }, [flow.usableAgentModels, query])

  const catalogMatches = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return flow.availableModels.filter((model) => (
      !normalized
      || `${model.label} ${model.id} ${model.provider} ${model.owned_by || ''}`.toLowerCase().includes(normalized)
    ))
  }, [flow.availableModels, query])

  const catalogItems = useMemo<ModelPickerItem[]>(() => (
    catalogMatches.slice(0, 100).map((model) => ({
      id: model.id,
      title: model.label,
      subtitle: `${providerLabel(model.provider)} · ${model.id}`,
      metadata: model.context_window ? `${model.context_window.toLocaleString()} token context` : undefined,
    }))
  ), [catalogMatches])

  if (flow.inventoryLoading) {
    return (
      <div className="flex h-full min-h-72 items-center justify-center rounded-xl border border-border/80 bg-background/40">
        <p className="text-sm text-muted">Loading Project model inventory...</p>
      </div>
    )
  }

  if (flow.inventoryError) {
    return (
      <div className="flex h-full min-h-72 flex-col items-center justify-center rounded-xl border border-border/80 bg-background/40 px-6 text-center">
        <p className="text-sm font-medium text-white">Could not load the Project model inventory</p>
        <p className="mt-1 max-w-md text-xs leading-5 text-muted">Retry before selecting the model used by this Agent.</p>
        <Button type="button" size="sm" variant="outline" className="mt-4" onClick={flow.retryInventory}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      </div>
    )
  }

  const openNewModel = () => {
    setQuery('')
    flow.startNewModel()
  }

  const openExistingModels = () => {
    setQuery('')
    flow.showExistingModels()
  }

  const selectCatalogModel = (modelId: string) => {
    const model = flow.availableModels.find((item) => item.id === modelId)
    if (model) flow.selectCatalogModel(model)
  }

  const selectedConnection = flow.selectedCredential || flow.activeCredentials[0] || null
  const catalogResultNote = catalogMatches.length > 100
    ? `Showing the first 100 of ${catalogMatches.length.toLocaleString()} matching models. Refine the search to narrow the list.`
    : undefined

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_auto_minmax(0,1fr)] gap-4 overflow-hidden">
      {flow.activeCredentials.length === 0 ? (
        <section className="flex min-h-48 flex-col items-center justify-center rounded-xl border border-dashed border-border bg-background/40 px-6 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
            <Key className="h-5 w-5" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-white">No provider connection</h3>
          <p className="mt-1 max-w-md text-sm leading-6 text-muted">
            Connect OpenAI, OpenRouter or another OpenAI-compatible provider before selecting the Agent model.
          </p>
          <Button type="button" className="mt-5" onClick={() => setProviderModalOpen(true)}>Connect provider</Button>
        </section>
      ) : (
        <section className="flex min-h-16 items-center justify-between gap-4 overflow-hidden rounded-xl border border-border/80 bg-background/45 px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <CheckCircle2 className="h-5 w-5 shrink-0 text-primary-light" />
            <div className="min-w-0">
              <p className="text-xs text-muted">Provider connection</p>
              {flow.activeCredentials.length === 1 && selectedConnection ? (
                <p className="mt-0.5 truncate text-sm font-medium text-white" title={credentialDisplayLabel(selectedConnection)}>
                  {credentialDisplayLabel(selectedConnection)}
                </p>
              ) : (
                <Select
                  value={flow.selectedCredential?.id || ''}
                  onChange={(event) => flow.selectCredential(event.target.value)}
                  options={flow.activeCredentials.map((credential) => ({
                    value: credential.id,
                    label: credentialDisplayLabel(credential),
                  }))}
                  className="mt-1 min-w-64"
                />
              )}
            </div>
          </div>
          <Button type="button" size="sm" variant="ghost" onClick={() => setProviderModalOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add connection
          </Button>
        </section>
      )}

      {flow.activeCredentials.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {flow.usableAgentModels.length > 0 && (
              <Button
                type="button"
                size="sm"
                variant={flow.modelMode === 'existing' ? 'secondary' : 'outline'}
                onClick={openExistingModels}
              >
                Existing models
              </Button>
            )}
            <Button
              type="button"
              size="sm"
              variant={flow.modelMode !== 'existing' ? 'secondary' : 'outline'}
              onClick={openNewModel}
            >
              Add new model
            </Button>
          </div>
          {flow.modelMode !== 'existing' && (
            <div className="flex items-center gap-2">
              {flow.canUseCatalog && flow.modelMode === 'manual' && (
                <Button type="button" size="sm" variant="ghost" onClick={() => { setQuery(''); flow.useCatalogMode() }}>
                  Browse provider catalog
                </Button>
              )}
              <Button type="button" size="sm" variant="ghost" onClick={() => setManualModalOpen(true)}>
                Enter model ID manually
              </Button>
            </div>
          )}
        </div>
      )}

      {flow.activeCredentials.length > 0 && (
        <div className="h-full min-h-0 overflow-hidden">
          {flow.modelMode === 'existing' ? (
            <ModelPicker
              items={existingItems}
              selectedId={flow.selectedModel?.id}
              query={query}
              onQueryChange={setQuery}
              onSelect={flow.selectExistingModel}
              emptyTitle="No active generation models"
              emptyDescription="Add a new model using one of the Project provider connections."
            />
          ) : flow.modelMode === 'catalog' ? (
            flow.catalogError ? (
              <div className="flex h-full min-h-64 flex-col items-center justify-center rounded-xl border border-border/80 bg-background/40 px-6 text-center">
                <p className="text-sm font-medium text-white">Could not load the provider catalog</p>
                <p className="mt-1 text-xs leading-5 text-muted">Retry discovery or enter the model identifier manually.</p>
                <div className="mt-4 flex gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={flow.retryCatalog}>Retry</Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setManualModalOpen(true)}>Enter model ID</Button>
                </div>
              </div>
            ) : (
              <ModelPicker
                items={catalogItems}
                selectedId={flow.selectedCatalogModel?.id}
                query={query}
                onQueryChange={setQuery}
                onSelect={selectCatalogModel}
                loading={flow.catalogLoading}
                emptyTitle="No catalog models found"
                emptyDescription="Try another search or enter the model identifier manually."
                resultNote={catalogResultNote}
              />
            )
          ) : (
            <div className="flex h-full min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-border bg-background/40 px-6 text-center">
              {flow.manualModelIdentifier ? (
                <>
                  <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted/75">Manual model</p>
                  <h3 className="mt-2 text-base font-semibold text-white">{flow.manualModelName || flow.manualModelIdentifier}</h3>
                  <p className="mt-1 max-w-lg truncate font-mono text-xs text-muted" title={flow.manualModelIdentifier}>{flow.manualModelIdentifier}</p>
                  <Button type="button" size="sm" variant="outline" className="mt-4" onClick={() => setManualModalOpen(true)}>Edit model ID</Button>
                </>
              ) : (
                <>
                  <h3 className="text-base font-semibold text-white">Enter the provider model ID</h3>
                  <p className="mt-1 max-w-md text-sm leading-6 text-muted">This provider does not expose a compatible model catalog, or the model is not listed.</p>
                  <Button type="button" className="mt-5" onClick={() => setManualModalOpen(true)}>Enter model ID</Button>
                </>
              )}
            </div>
          )}
        </div>
      )}

      <ProviderConnectionModal
        open={providerModalOpen}
        onClose={() => setProviderModalOpen(false)}
        projectId={projectId}
        existingCredentials={flow.credentials}
        onCreated={flow.registerCreatedCredential}
      />
      <ManualModelModal
        open={manualModalOpen}
        onClose={() => setManualModalOpen(false)}
        initialIdentifier={flow.manualModelIdentifier}
        initialName={flow.manualModelName}
        onConfirm={flow.setManualModel}
      />
    </div>
  )
}