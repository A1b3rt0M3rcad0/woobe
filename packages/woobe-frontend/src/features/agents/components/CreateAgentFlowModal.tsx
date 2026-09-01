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
      <ScrollArea className="h-[330px] rounded-lg border border-border/80 bg-background/30 p-2">
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, index) => <div key={index} className="h-14 animate-pulse rounded-lg bg-surface/70" />)}
          </div>
        ) : items.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-muted">No generation models found.</div>
        ) : (
          <div className="divide-y divide-border/60">
            {items.map((item) => {
              const selected = item.id === selectedId
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelect(item.id)}
                  aria-pressed={selected}
                  className={`flex min-h-14 w-full items-center justify-between gap-4 px-3 py-2.5 text-left transition-colors ${
                    selected ? 'bg-primary/[0.08]' : 'hover:bg-background/55'
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-white">{item.title}</span>
                    <span className="mt-0.5 block truncate font-mono text-[10px] text-muted">{item.subtitle}</span>
                  </span>
                  <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${selected ? 'border-primary bg-primary text-white' : 'border-border bg-background'}`}>
                    {selected ? <Check className="h-3 w-3" /> : null}
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
      <div className="max-w-3xl">
        <div className="mb-4 border-b border-border/70 pb-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary-light">Provider connection</p>
          <h3 className="mt-1 text-base font-semibold text-white">Connect a model provider</h3>
          <p className="mt-1 text-xs leading-5 text-muted">Create the credential without leaving the Agent creation flow.</p>
        </div>
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
          {flow.activeCredentials.length > 0 ? (
            <Button type="button" variant="outline" onClick={() => setShowProviderForm(false)} disabled={providerPending}>Back</Button>
          ) : null}
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
    <div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
      <aside className="border-b border-border/70 pb-5 lg:border-b-0 lg:border-r lg:pb-0 lg:pr-5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Provider</p>
        <div className="mt-3 flex items-start gap-2.5">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
          <div className="min-w-0">
            <p className="text-xs text-muted">Connection</p>
            {flow.activeCredentials.length === 1 ? (
              <p className="mt-1 truncate text-sm font-medium text-white">{flow.selectedCredential?.name || flow.activeCredentials[0].name}</p>
            ) : (
              <Select
                value={flow.selectedCredential?.id || ''}
                onChange={(event) => flow.selectCredential(event.target.value)}
                options={flow.activeCredentials.map((credential) => ({ value: credential.id, label: `${credential.name} · ${providerLabel(credential.provider)}` }))}
                className="mt-2 w-full"
              />
            )}
          </div>
        </div>
        <Button type="button" size="sm" variant="ghost" className="mt-3 w-full justify-start" onClick={() => setShowProviderForm(true)}>
          <Plus className="mr-2 h-4 w-4" />Add connection
        </Button>

        <div className="mt-5 border-t border-border/70 pt-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Model source</p>
          <div className="mt-2 space-y-1">
            {flow.usableAgentModels.length > 0 ? (
              <Button type="button" size="sm" variant={flow.modelMode === 'existing' ? 'secondary' : 'ghost'} className="w-full justify-start" onClick={() => { setQuery(''); flow.showExistingModels() }}>
                Existing models
              </Button>
            ) : null}
            <Button type="button" size="sm" variant={flow.modelMode !== 'existing' ? 'secondary' : 'ghost'} className="w-full justify-start" onClick={() => { setQuery(''); flow.startNewModel() }}>
              Add new model
            </Button>
            {flow.modelMode !== 'existing' && flow.canUseCatalog && flow.modelMode === 'manual' ? (
              <Button type="button" size="sm" variant="ghost" className="w-full justify-start" onClick={flow.useCatalogMode}>Browse provider catalog</Button>
            ) : null}
          </div>
        </div>
      </aside>

      <section className="min-w-0">
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary-light">Generation model</p>
          <h3 className="mt-1 text-base font-semibold text-white">Choose the model for this Agent</h3>
          <p className="mt-1 text-xs text-muted">The selected model becomes the Agent Draft generation configuration.</p>
        </div>

        {flow.modelMode === 'existing' ? (
          <SelectableModelList items={existingItems} selectedId={flow.selectedModel?.id} onSelect={flow.selectExistingModel} query={query} onQueryChange={setQuery} />
        ) : flow.modelMode === 'catalog' ? (
          flow.catalogError ? (
            <div className="rounded-lg border border-border/80 bg-background/35 p-5 text-center">
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
              <label className="mb-1 block text-xs font-medium text-muted">Model ID</label>
              <Input value={flow.manualModelIdentifier} onChange={(event) => flow.setManualModel(event.target.value, flow.manualModelName)} placeholder="deepseek/deepseek-chat" className="font-mono text-xs" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">Display name <span className="font-normal text-muted/70">(optional)</span></label>
              <Input value={flow.manualModelName} onChange={(event) => flow.setManualModel(flow.manualModelIdentifier, event.target.value)} placeholder="Defaults to model ID" />
            </div>
          </div>
        )}
      </section>
    </div>
  )
}

const STEPS = [
  { id: 'details' as const, label: 'Agent details', detail: 'Identity and instructions' },
  { id: 'model' as const, label: 'Model', detail: 'Provider and generation model' },
  { id: 'review' as const, label: 'Review', detail: 'Confirm the initial Draft' },
]

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

  const currentIndex = flow.step === 'details' ? 0 : flow.step === 'model' ? 1 : 2

  return (
    <Dialog
      open={open}
      onClose={flow.busy ? () => undefined : onClose}
      title="Create agent"
      className="max-h-[calc(100svh-2rem)] max-w-[900px] overflow-hidden"
      contentClassName="p-0"
    >
      {flow.inventoryLoading ? (
        <div className="p-6"><AgentCreationPreparing /></div>
      ) : flow.inventoryError ? (
        <div className="p-6"><AgentCreationLoadError onRetry={flow.retryInventory} onCancel={onClose} /></div>
      ) : (
        <div className="grid h-[min(78svh,720px)] grid-rows-[minmax(0,1fr)_auto] overflow-hidden">
          <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] overflow-hidden lg:grid-cols-[210px_minmax(0,1fr)] lg:grid-rows-1">
            <aside className="border-b border-border bg-background/20 lg:border-b-0 lg:border-r">
              <div className="flex gap-1 overflow-x-auto p-3 lg:flex-col lg:overflow-visible">
                {STEPS.map((step, index) => {
                  const active = step.id === flow.step
                  const complete = index < currentIndex
                  return (
                    <div
                      key={step.id}
                      className={`flex min-w-[160px] items-start gap-2.5 rounded-lg border px-3 py-2.5 lg:min-w-0 ${
                        active
                          ? 'border-primary/35 bg-primary/[0.08]'
                          : 'border-transparent text-muted'
                      }`}
                    >
                      <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] ${active ? 'border-primary text-primary-light' : complete ? 'border-emerald-500/40 text-emerald-300' : 'border-border'}`}>
                        {complete ? <Check className="h-3 w-3" /> : index + 1}
                      </span>
                      <span className="min-w-0">
                        <span className={`block text-xs font-medium ${active || complete ? 'text-white' : 'text-muted'}`}>{step.label}</span>
                        <span className="mt-0.5 hidden text-[10px] leading-4 text-muted lg:block">{step.detail}</span>
                      </span>
                    </div>
                  )
                })}
              </div>
            </aside>

            <ScrollArea className="min-h-0 bg-surface/35">
              <div className="p-5">
                {flow.step === 'details' ? (
                  <div>
                    <div className="mb-5">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary-light">Agent Draft</p>
                      <h3 className="mt-1 text-base font-semibold text-white">Define the Agent identity</h3>
                      <p className="mt-1 text-xs leading-5 text-muted">Keep the identity concise. Instructions receive the primary editing space.</p>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-xs font-medium text-muted">Name</label>
                        <Input value={flow.agentName} onChange={(event) => flow.setAgentName(event.target.value)} placeholder="Customer Support Agent" autoFocus />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-muted">Description <span className="font-normal text-muted/70">(optional)</span></label>
                        <Input value={flow.agentDescription} onChange={(event) => flow.setAgentDescription(event.target.value)} placeholder="Handles customer questions and support requests" />
                      </div>
                      <div className="md:col-span-2">
                        <div className="mb-1 flex items-center justify-between gap-3">
                          <label className="text-xs font-medium text-muted">Instructions</label>
                          <span className="text-[10px] text-muted">Initial Draft</span>
                        </div>
                        <Textarea value={flow.agentInstructions} onChange={(event) => flow.setAgentInstructions(event.target.value)} rows={12} placeholder="You are a customer support Agent. Answer clearly and do not invent information." className="min-h-[260px]" />
                      </div>
                    </div>
                  </div>
                ) : null}

                {flow.step === 'model' ? <ModalModelStep flow={flow} projectId={projectId} /> : null}

                {flow.step === 'review' && flow.selectedModel ? (
                  <div>
                    <div className="mb-5">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary-light">Review</p>
                      <h3 className="mt-1 text-base font-semibold text-white">Confirm the initial Agent Draft</h3>
                      <p className="mt-1 text-xs text-muted">Creation does not publish a Production release.</p>
                    </div>
                    <div className="grid gap-5 md:grid-cols-2">
                      <section className="border-b border-border/70 pb-4 md:border-b-0 md:border-r md:pb-0 md:pr-5">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Agent</p>
                        <p className="mt-2 text-base font-semibold text-white">{flow.agentName}</p>
                        <p className="mt-2 text-sm leading-5 text-muted">{flow.agentDescription || 'No description'}</p>
                      </section>
                      <section>
                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Model</p>
                        <p className="mt-2 text-base font-semibold text-white">{flow.selectedModel.name}</p>
                        <p className="mt-2 truncate font-mono text-[11px] text-muted">{providerLabel(flow.selectedModel.provider)} · {flow.selectedModel.model}</p>
                      </section>
                      <section className="border-t border-border/70 pt-5 md:col-span-2">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Instructions</p>
                        <div className="mt-3 max-h-[280px] overflow-y-auto rounded-lg border border-border/70 bg-background/30 p-4">
                          <p className="whitespace-pre-wrap text-sm leading-6 text-white/90">{flow.agentInstructions}</p>
                        </div>
                      </section>
                    </div>
                  </div>
                ) : null}
              </div>
            </ScrollArea>
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-border bg-surface/95 px-5 py-4 backdrop-blur">
            <Button type="button" variant="outline" onClick={onClose} disabled={flow.busy}>Cancel</Button>
            <div className="flex gap-2">
              {flow.step !== 'details' ? (
                <Button type="button" variant="outline" onClick={flow.goBack} disabled={flow.busy}>
                  <ArrowLeft className="mr-2 h-4 w-4" />Back
                </Button>
              ) : null}
              {footerPrimary()}
            </div>
          </div>
        </div>
      )}
    </Dialog>
  )
}
