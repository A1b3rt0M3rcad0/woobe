import { useEffect, useMemo, useState } from 'react'
import { Check, Cpu, KeyRound, Pencil, Plus, Search } from 'lucide-react'
import { toast } from 'sonner'
import {
  Button,
  Dialog,
  EmptyStatePanel,
  Field,
  FieldDescription,
  FieldLabel,
  Input,
  SectionBlock,
  Select,
  TechnicalListItem,
} from '@woobe/ui'

import { useCreateCredential, useCredentials, useUpdateCredential } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { buildModelProviderCredentialMetadata, isOpenAICompatibleProvider, modelProviderLabel, MODEL_PROVIDER_OPTIONS } from '@/features/provider-credentials/providers'
import { useAvailableProviderModels, useCreateProviderModel, useProviderModels, useUpdateProviderModel } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'

type Screen = 'list' | 'model' | 'credential'

interface Props {
  open: boolean
  projectId: string
  selectedModelId: string | null
  onClose: () => void
  onUseModel: (model: ProviderModel, credential?: ProviderCredential | null) => void
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

  const catalogQuery = useAvailableProviderModels(
    projectId,
    screen === 'model' && credentialId && !editingModel ? credentialId : undefined,
    'generation',
  )
  const selectedCredential = credentials.find((item) => item.id === credentialId) || null
  const selectedCatalog = (catalogQuery.data ?? []).find((item) => item.id === catalogId) || null
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return models.filter((model) => (
      model.status !== 'archived'
      && (!normalized || `${model.name} ${model.model} ${model.provider || ''}`.toLowerCase().includes(normalized))
    ))
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
    if (isOpenAICompatibleProvider(provider) && !baseUrl.trim()) return toast.error('Base URL is required')

    try {
      if (editingCredential) {
        await updateCredential.mutateAsync({
          id: editingCredential.id,
          data: {
            name: connectionName.trim(),
            provider,
            ...(secret.trim() ? { secret: secret.trim() } : {}),
            metadata: buildModelProviderCredentialMetadata(provider, baseUrl),
          },
        })
        setCredentialId(editingCredential.id)
      } else {
        const created = await createCredential.mutateAsync({
          project_id: projectId,
          provider,
          name: connectionName.trim(),
          secret: secret.trim(),
          metadata: buildModelProviderCredentialMetadata(provider, baseUrl),
        })
        setCredentialId(created.id)
      }
      await credentialsQuery.refetch()
      toast.success('Provider connection saved')
      setScreen('model')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save connection')
    }
  }

  const saveModel = async () => {
    const resolvedId = (selectedCatalog?.id || modelId).trim()
    const resolvedName = (selectedCatalog?.label || displayName || resolvedId).trim()
    if (!credentialId) return toast.error('Choose a provider connection')
    if (!resolvedId || !resolvedName) return toast.error('Model name and ID are required')

    const selectedSpec = selectedCatalog?.raw?.woobe_model_spec
    const metadata = {
      ...(editingModel?.metadata || {}),
      capability: selectedCatalog?.model_type || editingModel?.model_type || 'generation',
      source: selectedCatalog ? 'remote' : 'manual',
      ...(selectedCatalog?.raw ? { provider_model_raw: selectedCatalog.raw } : {}),
      pricing: {
        input_cost_per_1m_tokens: inputCost.trim() ? Number(inputCost) : null,
        output_cost_per_1m_tokens: outputCost.trim() ? Number(outputCost) : null,
        currency: currency.trim().toUpperCase() || 'USD',
        billing_unit: 'per_1m_tokens',
      },
    }

    try {
      const saved = editingModel
        ? await updateModel.mutateAsync({
            id: editingModel.id,
            data: {
              provider_credential_id: credentialId,
              name: resolvedName,
              model: resolvedId,
              ...(selectedCatalog?.model_type ? { model_type: selectedCatalog.model_type } : {}),
              ...(selectedSpec && typeof selectedSpec === 'object' ? { spec: selectedSpec as Record<string, any> } : {}),
              status,
              metadata,
            },
          })
        : await createModel.mutateAsync({
            project_id: projectId,
            provider_credential_id: credentialId,
            name: resolvedName,
            model: resolvedId,
            model_type: selectedCatalog?.model_type || undefined,
            spec: selectedSpec && typeof selectedSpec === 'object' ? selectedSpec as Record<string, any> : undefined,
            metadata,
          })
      await modelsQuery.refetch()
      onUseModel(saved, credentials.find((item) => item.id === credentialId) || selectedCredential)
      toast.success(editingModel ? 'Model updated and selected' : 'Model created and selected')
      onClose()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save model')
    }
  }

  const busy = createCredential.isPending || updateCredential.isPending || createModel.isPending || updateModel.isPending

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Manage models"
      className="flex max-h-dialog max-w-dialog-wide flex-col overflow-hidden"
      contentClassName="min-h-0 flex-1 p-0"
    >
      <div className="flex h-full min-h-0 flex-col">
        {screen === 'list' ? (
          <>
            <div className="flex shrink-0 flex-wrap gap-ui-sm border-b border-border bg-background/15 p-ui-md">
              <div className="relative min-w-0 flex-1">
                <Search className="pointer-events-none absolute left-ui-md top-1/2 h-icon w-icon -translate-y-1/2 text-muted-foreground" />
                <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models..." className="pl-9" />
              </div>
              <Button size="sm" variant="outline" onClick={() => openConnection()}>
                <KeyRound className="h-icon-sm w-icon-sm" />Connect
              </Button>
              <Button size="sm" onClick={() => openModel()}>
                <Plus className="h-icon-sm w-icon-sm" />New model
              </Button>
            </div>

            <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-ui-md">
              {filtered.length === 0 ? (
                <EmptyStatePanel compact title="No models configured" description="Connect a provider and create the first reusable generation model." />
              ) : (
                <div className="grid gap-ui-xs">
                  {filtered.map((model) => {
                    const credential = credentials.find((item) => item.id === model.provider_credential_id)
                    const selected = model.id === selectedModelId
                    return (
                      <TechnicalListItem
                        key={model.id}
                        label={model.name}
                        description={model.model}
                        meta={`${modelProviderLabel(model.provider || credential?.provider)} · ${credential?.name || 'Missing connection'}`}
                        selected={selected}
                        leading={(
                          <span className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-border bg-control text-primary-light">
                            <Cpu className="h-icon w-icon" />
                          </span>
                        )}
                        trailing={(
                          <div className="flex items-center gap-ui-sm">
                            {selected ? <Check className="h-icon w-icon text-primary-light" /> : null}
                            <Button size="sm" variant="ghost" onClick={(event) => { event.stopPropagation(); openModel(model) }}>
                              <Pencil className="h-icon-sm w-icon-sm" />Edit
                            </Button>
                            <Button size="sm" onClick={(event) => { event.stopPropagation(); onUseModel(model, credential); onClose() }}>
                              Use model
                            </Button>
                          </div>
                        )}
                        onClick={() => {
                          onUseModel(model, credential)
                          onClose()
                        }}
                      />
                    )
                  })}
                </div>
              )}
            </div>
          </>
        ) : screen === 'credential' ? (
          <>
            <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-ui-lg">
              <div className="mx-auto max-w-dialog-content">
                <SectionBlock
                  title={editingCredential ? 'Edit provider connection' : 'Connect provider'}
                  description="Store provider credentials separately from the Agent Draft."
                >
                  <div className="grid gap-ui-md">
                    <Field>
                      <FieldLabel>Provider</FieldLabel>
                      <Select value={provider} onChange={(event) => setProvider(event.target.value)} options={MODEL_PROVIDER_OPTIONS} />
                    </Field>
                    <Field>
                      <FieldLabel>Connection name</FieldLabel>
                      <Input value={connectionName} onChange={(event) => setConnectionName(event.target.value)} />
                    </Field>
                    {isOpenAICompatibleProvider(provider) ? (
                      <Field>
                        <FieldLabel>Base URL</FieldLabel>
                        <Input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} className="font-mono" />
                      </Field>
                    ) : null}
                    <Field>
                      <FieldLabel>{editingCredential ? 'Replace API key (optional)' : 'API key'}</FieldLabel>
                      <Input type="password" value={secret} onChange={(event) => setSecret(event.target.value)} />
                      {editingCredential ? <FieldDescription>Leave empty to keep the currently stored secret.</FieldDescription> : null}
                    </Field>
                  </div>
                </SectionBlock>
              </div>
            </div>
            <div className="flex shrink-0 justify-end gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md">
              <Button variant="outline" onClick={() => setScreen(editingModel || credentialId ? 'model' : 'list')}>Cancel</Button>
              <Button onClick={() => void saveConnection()} loading={createCredential.isPending || updateCredential.isPending}>Save connection</Button>
            </div>
          </>
        ) : (
          <>
            <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-ui-lg">
              <div className="mx-auto max-w-dialog-content">
                <SectionBlock
                  title={editingModel ? 'Edit model' : 'Create model'}
                  description="Bind a generation model to one provider connection and optional pricing metadata."
                >
                  <div className="grid gap-ui-md">
                    <div className="flex items-end gap-ui-sm">
                      <Field className="min-w-0 flex-1">
                        <FieldLabel>Provider connection</FieldLabel>
                        <Select
                          value={credentialId}
                          onChange={(event) => {
                            setCredentialId(event.target.value)
                            setCatalogId('')
                          }}
                          options={[
                            { value: '', label: 'Select a connection' },
                            ...credentials
                              .filter((item) => item.status !== 'inactive')
                              .map((item) => ({ value: item.id, label: `${item.name} · ${modelProviderLabel(item.provider)}` })),
                          ]}
                        />
                      </Field>
                      <Button size="sm" variant="outline" onClick={() => openConnection(selectedCredential)}>
                        {selectedCredential ? 'Edit connection' : 'Connect'}
                      </Button>
                    </div>

                    {!editingModel && credentialId && (catalogQuery.data?.length || 0) > 0 ? (
                      <Field>
                        <FieldLabel>Provider catalog</FieldLabel>
                        <Select
                          value={catalogId}
                          onChange={(event) => {
                            const item = catalogQuery.data?.find((model) => model.id === event.target.value)
                            setCatalogId(event.target.value)
                            if (item) {
                              setModelId(item.id)
                              setDisplayName(item.label)
                            }
                          }}
                          options={[
                            { value: '', label: 'Enter model manually' },
                            ...(catalogQuery.data ?? []).slice(0, 100).map((item) => ({ value: item.id, label: `${item.label} · ${item.id}` })),
                          ]}
                        />
                      </Field>
                    ) : null}

                    <div className="grid gap-ui-md sm:grid-cols-2">
                      <Field>
                        <FieldLabel>Display name</FieldLabel>
                        <Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
                      </Field>
                      <Field>
                        <FieldLabel>Model ID</FieldLabel>
                        <Input className="font-mono" value={modelId} onChange={(event) => setModelId(event.target.value)} />
                      </Field>
                      <Field>
                        <FieldLabel>Input / 1M</FieldLabel>
                        <Input type="number" min="0" step="0.000001" value={inputCost} onChange={(event) => setInputCost(event.target.value)} />
                      </Field>
                      <Field>
                        <FieldLabel>Output / 1M</FieldLabel>
                        <Input type="number" min="0" step="0.000001" value={outputCost} onChange={(event) => setOutputCost(event.target.value)} />
                      </Field>
                      <Field>
                        <FieldLabel>Currency</FieldLabel>
                        <Input className="uppercase" maxLength={3} value={currency} onChange={(event) => setCurrency(event.target.value)} />
                      </Field>
                      {editingModel ? (
                        <Field>
                          <FieldLabel>Status</FieldLabel>
                          <Select
                            value={status}
                            onChange={(event) => setStatus(event.target.value)}
                            options={[
                              { value: 'active', label: 'Active' },
                              { value: 'inactive', label: 'Inactive' },
                              { value: 'archived', label: 'Archived' },
                            ]}
                          />
                        </Field>
                      ) : null}
                    </div>
                  </div>
                </SectionBlock>
              </div>
            </div>
            <div className="flex shrink-0 justify-end gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md">
              <Button variant="outline" onClick={() => setScreen('list')} disabled={busy}>Cancel</Button>
              <Button onClick={() => void saveModel()} loading={createModel.isPending || updateModel.isPending}>
                {editingModel ? 'Save and use' : 'Create and use'}
              </Button>
            </div>
          </>
        )}
      </div>
    </Dialog>
  )
}
