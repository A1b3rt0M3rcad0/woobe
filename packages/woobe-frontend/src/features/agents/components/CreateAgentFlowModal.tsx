import { useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, Plus, Search, ShieldCheck } from 'lucide-react'
import {
  Alert,
  AlertDescription,
  Button,
  Dialog,
  DialogBody,
  DialogContextBar,
  DialogFooter,
  EmptyStatePanel,
  Field,
  FieldDescription,
  FieldLabel,
  Input,
  InputGroup,
  ScrollArea,
  SectionBlock,
  SegmentedControl,
  Select,
  Skeleton,
  Stepper,
  TechnicalListItem,
  Textarea,
} from '@woobe/ui'

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
    <div className="grid gap-ui-sm">
      <InputGroup start={<Search />}>
        <Input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="Search models" />
      </InputGroup>

      <ScrollArea className="h-60 rounded-container border border-border bg-background/25 p-ui-xs">
        {loading ? (
          <div className="grid gap-ui-xs">
            {Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-control-row w-full" />)}
          </div>
        ) : items.length === 0 ? (
          <EmptyStatePanel compact variant="plain" title="No generation models found" description="Change the search or configure a new model." />
        ) : (
          <div className="grid gap-ui-xs">
            {items.map((item) => (
              <TechnicalListItem
                key={item.id}
                label={item.title}
                description={item.subtitle}
                selected={item.id === selectedId}
                density="compact"
                trailing={item.id === selectedId ? <Check className="h-icon w-icon text-primary-light" /> : null}
                onClick={() => onSelect(item.id)}
              />
            ))}
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
      <div className="mx-auto max-w-dialog-content">
        <SectionBlock
          eyebrow="Provider connection"
          title="Connect a model provider"
          description="Create the Project credential without leaving the Agent creation flow."
        >
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
          <div className="mt-ui-md flex justify-end gap-ui-sm border-t border-border pt-ui-md">
            {flow.activeCredentials.length > 0 ? (
              <Button type="button" variant="outline" onClick={() => setShowProviderForm(false)} disabled={providerPending}>Back</Button>
            ) : null}
            <Button type="submit" form="create-agent-provider-form" loading={providerPending}>Connect provider</Button>
          </div>
        </SectionBlock>
      </div>
    )
  }

  const selectCatalog = (id: string) => {
    const model = flow.availableModels.find((item) => item.id === id)
    if (model) flow.selectCatalogModel(model)
  }

  const sourceItems = [
    ...(flow.usableAgentModels.length > 0 ? [{ value: 'existing', label: 'Existing models' }] : []),
    { value: 'new', label: flow.canUseCatalog ? 'Provider catalog' : 'Manual model' },
  ]
  const sourceValue = flow.modelMode === 'existing' ? 'existing' : 'new'

  return (
    <div className="grid gap-ui-md lg:grid-cols-12">
      <aside className="grid content-start gap-ui-md lg:col-span-4">
        <SectionBlock title="Provider" description="Select the Project connection used by this generation model.">
          <div className="grid gap-ui-sm">
            {flow.activeCredentials.length === 1 ? (
              <TechnicalListItem
                label={flow.selectedCredential?.name || flow.activeCredentials[0].name}
                description={providerLabel(flow.selectedCredential?.provider || flow.activeCredentials[0].provider)}
                selected
                density="compact"
                trailing={<Check className="h-icon w-icon text-primary-light" />}
              />
            ) : (
              <Field>
                <FieldLabel>Connection</FieldLabel>
                <Select
                  value={flow.selectedCredential?.id || ''}
                  onChange={(event) => flow.selectCredential(event.target.value)}
                  options={flow.activeCredentials.map((credential) => ({
                    value: credential.id,
                    label: `${credential.name} · ${providerLabel(credential.provider)}`,
                  }))}
                />
              </Field>
            )}
            <Button type="button" size="sm" variant="outline" onClick={() => setShowProviderForm(true)}>
              <Plus className="h-icon-sm w-icon-sm" />Add connection
            </Button>
          </div>
        </SectionBlock>

        <SectionBlock title="Model source" description="Reuse a Project model or add a provider model.">
          <SegmentedControl
            items={sourceItems}
            value={sourceValue}
            onValueChange={(value) => {
              setQuery('')
              if (value === 'existing') flow.showExistingModels()
              else flow.startNewModel()
            }}
            ariaLabel="Generation model source"
            stretch
            size="segment"
          />
          {flow.modelMode !== 'existing' && flow.canUseCatalog && flow.modelMode === 'manual' ? (
            <Button type="button" size="sm" variant="ghost" className="mt-ui-sm" onClick={flow.useCatalogMode}>Browse provider catalog</Button>
          ) : null}
        </SectionBlock>
      </aside>

      <section className="min-w-0 lg:col-span-8">
        <SectionBlock
          eyebrow="Generation model"
          title="Choose the model for this Agent"
          description="The selected model becomes the Agent Draft generation configuration."
        >
          {flow.modelMode === 'existing' ? (
            <SelectableModelList items={existingItems} selectedId={flow.selectedModel?.id} onSelect={flow.selectExistingModel} query={query} onQueryChange={setQuery} />
          ) : flow.modelMode === 'catalog' ? (
            flow.catalogError ? (
              <Alert variant="warning">
                <AlertDescription>Could not load the provider catalog.</AlertDescription>
                <div className="mt-ui-md flex gap-ui-sm">
                  <Button type="button" size="sm" variant="outline" onClick={flow.retryCatalog}>Retry</Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => flow.setManualModel('', '')}>Enter model ID</Button>
                </div>
              </Alert>
            ) : (
              <SelectableModelList items={catalogItems} selectedId={flow.selectedCatalogModel?.id} onSelect={selectCatalog} query={query} onQueryChange={setQuery} loading={flow.catalogLoading} />
            )
          ) : (
            <div className="grid gap-ui-md sm:grid-cols-2">
              <Field>
                <FieldLabel>Model ID</FieldLabel>
                <Input value={flow.manualModelIdentifier} onChange={(event) => flow.setManualModel(event.target.value, flow.manualModelName)} placeholder="deepseek/deepseek-chat" className="font-mono" />
              </Field>
              <Field>
                <FieldLabel>Display name <span className="font-normal text-muted-foreground">(optional)</span></FieldLabel>
                <Input value={flow.manualModelName} onChange={(event) => flow.setManualModel(flow.manualModelIdentifier, event.target.value)} placeholder="Defaults to model ID" />
              </Field>
            </div>
          )}
        </SectionBlock>
      </section>
    </div>
  )
}

const STEPS = [
  { id: 'details' as const, label: 'Agent details', detail: 'Identity and objective' },
  { id: 'model' as const, label: 'Model', detail: 'Provider and model' },
  { id: 'review' as const, label: 'Review', detail: 'Confirm Draft' },
]

export function CreateAgentFlowModal({ open, onClose, projectId, onCreated }: CreateAgentFlowModalProps) {
  const flow = useAgentCreationFlow({ projectId, onCreated, active: open })

  const footerPrimary = () => {
    if (flow.step === 'details') {
      return (
        <Button type="button" onClick={flow.continueFromDetails}>
          Continue<ArrowRight className="h-icon w-icon" />
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
        <ShieldCheck className="h-icon w-icon" />Create agent
      </Button>
    )
  }

  const currentIndex = flow.step === 'details' ? 0 : flow.step === 'model' ? 1 : 2
  const stepperItems = STEPS.map((step, index) => ({
    id: step.id,
    label: step.label,
    description: step.detail,
    state: index < currentIndex ? 'complete' as const : index === currentIndex ? 'current' as const : 'pending' as const,
  }))

  return (
    <Dialog
      open={open}
      onClose={flow.busy ? () => undefined : onClose}
      title="Create agent"
      variant="workspace"
    >
      {flow.inventoryLoading ? (
        <DialogBody><AgentCreationPreparing /></DialogBody>
      ) : flow.inventoryError ? (
        <DialogBody><AgentCreationLoadError onRetry={flow.retryInventory} onCancel={onClose} /></DialogBody>
      ) : (
        <div className="flex min-h-0 flex-col overflow-hidden">
          <DialogContextBar>
            <Stepper items={stepperItems} />
          </DialogContextBar>

          <DialogBody className="bg-surface/25">
            {flow.step === 'details' ? (
              <SectionBlock
                eyebrow="Agent Draft"
                title="Define the Agent identity"
                description="Define the role and primary outcome. Configure the full Behavior in the Agent editor."
              >
                <div className="grid gap-ui-md md:grid-cols-2">
                  <Field>
                    <FieldLabel>Name</FieldLabel>
                    <Input value={flow.agentName} onChange={(event) => flow.setAgentName(event.target.value)} placeholder="Customer Support Agent" autoFocus />
                  </Field>
                  <Field>
                    <FieldLabel>Description <span className="font-normal text-muted-foreground">(optional)</span></FieldLabel>
                    <Input value={flow.agentDescription} onChange={(event) => flow.setAgentDescription(event.target.value)} placeholder="Handles customer questions and support requests" />
                  </Field>
                  <Field className="md:col-span-2">
                    <FieldLabel>Objective</FieldLabel>
                    <Textarea value={flow.agentObjective} onChange={(event) => flow.setAgentObjective(event.target.value)} aria-label="Objective" rows={4} placeholder="Resolve customer support requests accurately." />
                    <FieldDescription>Initial Draft objective. Detailed Behavior can be configured after creation.</FieldDescription>
                  </Field>
                </div>
              </SectionBlock>
            ) : null}

            {flow.step === 'model' ? <ModalModelStep flow={flow} projectId={projectId} /> : null}

            {flow.step === 'review' && flow.selectedModel ? (
              <div className="grid gap-ui-md">
                <SectionBlock eyebrow="Review" title="Confirm the initial Agent Draft" description="Creation does not publish a Production release." />
                <div className="grid gap-ui-md md:grid-cols-2">
                  <SectionBlock title="Agent">
                    <TechnicalListItem density="compact" label={flow.agentName} description={flow.agentDescription || 'No description'} />
                  </SectionBlock>
                  <SectionBlock title="Model">
                    <TechnicalListItem density="compact" label={flow.selectedModel.name} description={`${providerLabel(flow.selectedModel.provider)} · ${flow.selectedModel.model}`} />
                  </SectionBlock>
                  <SectionBlock title="Objective" className="md:col-span-2">
                    <p className="whitespace-pre-wrap font-sans text-product-caption text-accent-foreground/90">{flow.agentObjective}</p>
                  </SectionBlock>
                </div>
              </div>
            ) : null}
          </DialogBody>

          <DialogFooter
            actions={(
              <>
                <Button type="button" variant="outline" onClick={onClose} disabled={flow.busy}>Cancel</Button>
                {flow.step !== 'details' ? (
                  <Button type="button" variant="outline" onClick={flow.goBack} disabled={flow.busy}>
                    <ArrowLeft className="h-icon w-icon" />Back
                  </Button>
                ) : null}
                {footerPrimary()}
              </>
            )}
          />
        </div>
      )}
    </Dialog>
  )
}
