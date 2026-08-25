import { useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Plus, Search, ShieldCheck } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { AgentCreationLoadError, AgentCreationPreparing } from '@/features/agents/components/AgentCreationBootstrap'
import {
  providerLabel,
  useAgentCreationFlow,
  type AgentCreationFlowController,
} from '@/features/agents/hooks/useAgentCreationFlow'
import type { Agent } from '@/features/agents/types'
import { ProviderCredentialCreateForm } from '@/features/provider-credentials/components/ProviderCredentialCreateForm'

interface CreateAgentFlowModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  onCreated: (agent: Agent) => void
}

interface SelectableItem {
  id: string
  title: string
  subtitle: string
}

function SelectableModelList({
  items,
  selectedId,
  onSelect,
  query,
  onQueryChange,
  loading = false,
}: {
  items: SelectableItem[]
  selectedId?: string
  onSelect: (id: string) => void
  query: string
  onQueryChange: (query: string) => void
  loading?: boolean
}) {
  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="Search models" className="pl-9" />
      </div>
      <ScrollArea className="max-h-80 rounded-xl border border-border/80 bg-background/40 p-2">
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, index) => <div key={index} className="h-14 animate-pulse rounded-lg bg-surface/70" />)}
          </div>
        ) : items.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-muted">No generation models found.</div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => {
              const selected = item.id === selectedId
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelect(item.id)}
                  aria-pressed={selected}
                  className={`flex min-h-14 w-full items-center justify-between gap-4 rounded-lg border px-4 py-2.5 text-left transition-colors ${
                    selected ? 'border-primary/55 bg-primary/[0.08]' : 'border-border/70 bg-background/55 hover:border-primary/30'
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-white">{item.title}</span>
                    <span className="mt-0.5 block truncate text-xs text-muted">{item.subtitle}</span>
                  </span>
                  <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${selected ? 'border-primary bg-primary text-white' : 'border-border bg-background'}`}>
                    {selected && <Check className="h-3 w-3" />}
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}

function ModalModelStep({ flow, projectId }: { flow: AgentCreationFlowController; projectId: string }) {
  const [query, setQuery] = useState('')
  const [showProviderForm, setShowProviderForm] = useState(false)
  const [providerPending, setProviderPending] = useState(false)
  const providerFormVisible = showProviderForm || flow.activeCredentials.length === 0

  const existingItems = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return flow.usableAgentModels
      .filter((model) => !normalized || `${model.name} ${model.model} ${providerLabel(model.provider)}`.toLowerCase().includes(normalized))
      .map((model) => ({ id: model.id, title: model.name, subtitle: `${providerLabel(model.provider)} · ${model.model}` }))
  }, [flow.usableAgentModels, query])

  const catalogItems = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return flow.availableModels
      .filter((model) => !normalized || `${model.label} ${model.id} ${model.provider}`.toLowerCase().includes(normalized))
      .slice(0, 80)
      .map((model) => ({ id: model.id, title: model.label, subtitle: `${providerLabel(model.provider)} · ${model.id}` }))
  }, [flow.availableModels, query])

  if (providerFormVisible) {
    return (
      <div>
        <ProviderCredentialCreateForm
          projectId={projectId}
          existingCredentials={flow.credentials}
          formId="create-agent-provider-form"
          showActions={false}
          onPendingChange={setProviderPending}
          onCreated={(credential) => {
            flow.registerCreatedCredential(credential)
            setShowProviderForm(false)
          }}
        />
        <div className="mt-5 flex justify-end gap-2 border-t border-border/80 pt-4">
          {flow.activeCredentials.length > 0 && <Button type="button" variant="outline" onClick={() => setShowProviderForm(false)} disabled={providerPending}>Back</Button>}
          <Button type="submit" form="create-agent-provider-form" loading={providerPending}>Connect provider</Button>
        </div>
      </div>
    )
  }

  const selectCatalog = (id: string) => {
    const model = flow.availableModels.find((item) => item.id === id)
    if (model) flow.selectCatalogModel(model)
  }

  return (
    <div className="space-y-5">
      <section className="flex items-center justify-between gap-4 rounded-xl border border-border/80 bg-background/45 px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-primary-light" />
          <div className="min-w-0">
            <p className="text-xs text-muted">Provider connection</p>
            {flow.activeCredentials.length === 1 ? (
              <p className="mt-0.5 truncate text-sm font-medium text-white">{flow.selectedCredential?.name || flow.activeCredentials[0].name}</p>
            ) : (
              <Select
                value={flow.selectedCredential?.id || ''}
                onChange={(event) => flow.selectCredential(event.target.value)}
                options={flow.activeCredentials.map((credential) => ({ value: credential.id, label: `${credential.name} · ${providerLabel(credential.provider)}` }))}
                className="mt-1 min-w-64"
              />
            )}
          </div>
        </div>
        <Button type="button" size="sm" variant="ghost" onClick={() => setShowProviderForm(true)}>
          <Plus className="mr-2 h-4 w-4" />Add connection
        </Button>
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          {flow.usableAgentModels.length > 0 && (
            <Button type="button" size="sm" variant={flow.modelMode === 'existing' ? 'secondary' : 'outline'} onClick={() => { setQuery(''); flow.showExistingModels() }}>
              Existing models
            </Button>
          )}
          <Button type="button" size="sm" variant={flow.modelMode !== 'existing' ? 'secondary' : 'outline'} onClick={() => { setQuery(''); flow.startNewModel() }}>
            Add new model
          </Button>
        </div>
        {flow.modelMode !== 'existing' && flow.canUseCatalog && flow.modelMode === 'manual' && (
          <Button type="button" size="sm" variant="ghost" onClick={flow.useCatalogMode}>Browse provider catalog</Button>
        )}
      </div>

      {flow.modelMode === 'existing' ? (
        <SelectableModelList items={existingItems} selectedId={flow.selectedModel?.id} onSelect={flow.selectExistingModel} query={query} onQueryChange={setQuery} />
      ) : flow.modelMode === 'catalog' ? (
        flow.catalogError ? (
          <div className="rounded-xl border border-border/80 bg-background/45 p-5 text-center">
            <p className="text-sm font-medium text-white">Could not load provider catalog</p>
            <div className="mt-4 flex justify-center gap-2">
              <Button type="button" size="sm" variant="outline" onClick={flow.retryCatalog}>Retry</Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => flow.setManualModel('', '')}>Enter model ID</Button>
            </div>
          </div>
        ) : (
          <SelectableModelList items={catalogItems} selectedId={flow.selectedCatalogModel?.id} onSelect={selectCatalog} query={query} onQueryChange={setQuery} loading={flow.catalogLoading} />
        )
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Model ID</label>
            <Input value={flow.manualModelIdentifier} onChange={(event) => flow.setManualModel(event.target.value, flow.manualModelName)} placeholder="deepseek/deepseek-chat" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Display name <span className="font-normal text-muted/70">(optional)</span></label>
            <Input value={flow.manualModelName} onChange={(event) => flow.setManualModel(flow.manualModelIdentifier, event.target.value)} placeholder="Defaults to model ID" />
          </div>
        </div>
      )}
    </div>
  )
}

export function CreateAgentFlowModal({ open, onClose, projectId, onCreated }: CreateAgentFlowModalProps) {
  const flow = useAgentCreationFlow({ projectId, onCreated, active: open })

  const footerPrimary = () => {
    if (flow.step === 'details') {
      return (
        <Button type="button" onClick={flow.continueFromDetails}>
          Continue<ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      )
    }
    if (flow.step === 'model') {
      return (
        <Button type="button" onClick={() => { void flow.continueFromModel() }} loading={flow.creatingModel} disabled={!flow.canContinueModel}>
          {flow.modelMode === 'existing' ? 'Continue to review' : 'Add model and review'}
        </Button>
      )
    }
    return (
      <Button type="button" onClick={() => { void flow.createAgent() }} loading={flow.creatingAgent}>
        <ShieldCheck className="mr-2 h-4 w-4" />Create agent
      </Button>
    )
  }

  return (
    <Dialog open={open} onClose={flow.busy ? () => undefined : onClose} title="Create agent" className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden">
      {flow.inventoryLoading ? (
        <AgentCreationPreparing />
      ) : flow.inventoryError ? (
        <AgentCreationLoadError onRetry={flow.retryInventory} onCancel={onClose} />
      ) : (
        <div className="grid min-h-[520px] max-h-[calc(100svh-8rem)] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden">
          <div className="mb-5 grid grid-cols-3 gap-2 rounded-xl border border-border/80 bg-background/55 p-2">
            {(['details', 'model', 'review'] as const).map((step, index) => {
              const currentIndex = flow.step === 'details' ? 0 : flow.step === 'model' ? 1 : 2
              const active = step === flow.step
              const complete = index < currentIndex
              return (
                <div key={step} className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${active ? 'bg-primary/10 text-white' : complete ? 'text-white/85' : 'text-muted'}`}>
                  <span className={`flex h-6 w-6 items-center justify-center rounded-full border text-xs ${active ? 'border-primary' : 'border-border'}`}>
                    {complete ? <Check className="h-3.5 w-3.5" /> : index + 1}
                  </span>
                  {step === 'details' ? 'Agent details' : step === 'model' ? 'Model' : 'Review'}
                </div>
              )
            })}
          </div>

          <ScrollArea className="min-h-0 pr-1">
            {flow.step === 'details' && (
              <div className="space-y-4 rounded-xl border border-border/80 bg-surface/65 p-5">
                <div>
                  <label className="mb-1 block text-sm font-medium text-muted">Name</label>
                  <Input value={flow.agentName} onChange={(event) => flow.setAgentName(event.target.value)} placeholder="Customer Support Agent" autoFocus />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-muted">Description <span className="font-normal text-muted/70">(optional)</span></label>
                  <Input value={flow.agentDescription} onChange={(event) => flow.setAgentDescription(event.target.value)} placeholder="Handles customer questions and support requests" />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-muted">Instructions</label>
                  <Textarea value={flow.agentInstructions} onChange={(event) => flow.setAgentInstructions(event.target.value)} rows={7} placeholder="You are a customer support Agent. Answer clearly and do not invent information." />
                </div>
              </div>
            )}

            {flow.step === 'model' && <ModalModelStep flow={flow} projectId={projectId} />}

            {flow.step === 'review' && flow.selectedModel && (
              <div className="grid gap-4 sm:grid-cols-2">
                <section className="rounded-xl border border-border/80 bg-background/45 p-5">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted">Agent</p>
                  <p className="mt-2 text-base font-semibold text-white">{flow.agentName}</p>
                  <p className="mt-2 text-sm text-muted">{flow.agentDescription || 'No description'}</p>
                </section>
                <section className="rounded-xl border border-border/80 bg-background/45 p-5">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted">Model</p>
                  <p className="mt-2 text-base font-semibold text-white">{flow.selectedModel.name}</p>
                  <p className="mt-2 truncate text-xs text-muted">{providerLabel(flow.selectedModel.provider)} · {flow.selectedModel.model}</p>
                </section>
                <section className="rounded-xl border border-border/80 bg-background/45 p-5 sm:col-span-2">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted">Instructions</p>
                  <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-white/90">{flow.agentInstructions}</p>
                </section>
              </div>
            )}
          </ScrollArea>

          <div className="mt-5 flex items-center justify-between gap-3 border-t border-border pt-4">
            <Button type="button" variant="outline" onClick={onClose} disabled={flow.busy}>Cancel</Button>
            <div className="flex gap-2">
              {flow.step !== 'details' && (
                <Button type="button" variant="outline" onClick={flow.goBack} disabled={flow.busy}>
                  <ArrowLeft className="mr-2 h-4 w-4" />Back
                </Button>
              )}
              {footerPrimary()}
            </div>
          </div>
        </div>
      )}
    </Dialog>
  )
}
