import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Boxes, Key, Plus } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import type { ProviderModel } from '@/features/provider-models/types'
import { orgProjectPath } from '@/lib/constants/routes'
import { useAgentEditor } from '../AgentEditorContext'

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
  anthropic: 'Anthropic',
  google: 'Google',
  custom: 'Custom',
}

function providerLabel(provider?: string | null) {
  if (!provider) return 'Unknown'
  return providerLabels[provider] || provider
}

function getCredentialBaseUrl(credential?: ProviderCredential | null): string {
  return credential?.metadata?.base_url || ''
}

function getProviderModelProvider(model: ProviderModel, credential?: ProviderCredential | null) {
  return model.provider || credential?.provider || ''
}

function ModelSummary({
  model,
  credential,
  onChange,
  onRemove,
}: {
  model: ProviderModel
  credential?: ProviderCredential | null
  onChange: () => void
  onRemove: () => void
}) {
  const provider = getProviderModelProvider(model, credential)
  return (
    <div className="space-y-2 rounded-lg border border-border bg-background p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{providerLabel(provider)}</Badge>
            <span className="truncate text-sm font-medium">{model.name}</span>
          </div>
          <code className="mt-2 block truncate text-xs text-muted">{model.model}</code>
        </div>
        <Badge variant={model.status === 'active' ? 'success' : 'secondary'}>{model.status || 'active'}</Badge>
      </div>
      <div className="space-y-1 text-xs text-muted">
        <p>Credential: <span className="text-white/80">{credential?.name || 'Missing credential'}</span></p>
        {getCredentialBaseUrl(credential) && <p>Base URL: <code className="rounded bg-background px-1">{getCredentialBaseUrl(credential)}</code></p>}
      </div>
      <div className="flex gap-2">
        <Button type="button" size="sm" variant="outline" onClick={onChange}>Change</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onRemove}>Remove</Button>
      </div>
    </div>
  )
}

interface ModelSettingsTabProps {
  projectId: string
}

export function ModelSettingsTab({ projectId }: ModelSettingsTabProps) {
  const navigate = useNavigate()
  const { organizationId } = useParams<{ organizationId?: string }>()
  const { data: credentials = [], refetch: refetchCredentials } = useCredentials(projectId)
  const { data: providerModels = [], refetch: refetchProviderModels } = useProviderModels(projectId)
  const { state, setField } = useAgentEditor()

  const [showAddCredential, setShowAddCredential] = useState(false)
  const [changingPrimary, setChangingPrimary] = useState(false)
  const [changingFallback, setChangingFallback] = useState(false)

  const credentialsById = useMemo(() => new Map(credentials.map((credential) => [credential.id, credential])), [credentials])
  const activeModels = providerModels.filter((model) => model.status !== 'archived')

  const selectedModel = providerModels.find((model) => model.id === state.providerModelId) || null
  const selectedCredential = selectedModel ? credentialsById.get(selectedModel.provider_credential_id) : null
  const fallbackModel = providerModels.find((model) => model.id === state.fallbackProviderModelId) || null
  const fallbackCredential = fallbackModel ? credentialsById.get(fallbackModel.provider_credential_id) : null

  useEffect(() => {
    if (!selectedModel) return
    const credential = credentialsById.get(selectedModel.provider_credential_id)
    setField('providerCredentialId', selectedModel.provider_credential_id)
    setField('provider', selectedModel.provider || credential?.provider || state.provider)
    setField('model', selectedModel.model)
    setField('baseUrl', credential?.metadata?.base_url || null)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedModel?.id, credentialsById])

  useEffect(() => {
    if (!fallbackModel) return
    const credential = credentialsById.get(fallbackModel.provider_credential_id)
    setField('fallbackProviderCredentialId', fallbackModel.provider_credential_id)
    setField('fallbackProvider', fallbackModel.provider || credential?.provider || state.fallbackProvider)
    setField('fallbackModel', fallbackModel.model)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fallbackModel?.id, credentialsById])

  const handleSelectPrimaryModel = (id: string) => {
    const model = providerModels.find((item) => item.id === id)
    if (!model) return
    const credential = credentialsById.get(model.provider_credential_id)
    setField('providerModelId', model.id)
    setField('providerCredentialId', model.provider_credential_id)
    setField('provider', model.provider || credential?.provider || '')
    setField('model', model.model)
    setField('baseUrl', credential?.metadata?.base_url || null)
    setChangingPrimary(false)
  }

  const handleRemovePrimaryModel = () => {
    setField('providerModelId', null)
    setField('providerCredentialId', null)
    setField('provider', '')
    setField('model', '')
    setField('baseUrl', null)
    setChangingPrimary(true)
  }

  const handleSelectFallbackModel = (id: string) => {
    if (!id) {
      handleRemoveFallbackModel()
      return
    }
    const model = providerModels.find((item) => item.id === id)
    if (!model) return
    const credential = credentialsById.get(model.provider_credential_id)
    setField('fallbackProviderModelId', model.id)
    setField('fallbackProviderCredentialId', model.provider_credential_id)
    setField('fallbackProvider', model.provider || credential?.provider || '')
    setField('fallbackModel', model.model)
    setChangingFallback(false)
  }

  const handleRemoveFallbackModel = () => {
    setField('fallbackProviderModelId', null)
    setField('fallbackProviderCredentialId', null)
    setField('fallbackProvider', '')
    setField('fallbackModel', '')
    setChangingFallback(false)
  }

  const handleCredentialCreated = async () => {
    setShowAddCredential(false)
    await refetchCredentials()
  }

  const goToModelsPage = () => {
    navigate(orgProjectPath(organizationId, projectId, 'models'))
  }

  const selectOptions = [
    { value: '', label: 'Select a model' },
    ...activeModels.map((model) => {
      const credential = credentialsById.get(model.provider_credential_id)
      const provider = getProviderModelProvider(model, credential)
      return {
        value: model.id,
        label: `${model.name} · ${model.model} (${providerLabel(provider)})`,
      }
    }),
  ]

  return (
    <div className="space-y-4 p-4">
      <div className="rounded-xl border border-border bg-surface">
        <div className="space-y-3 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Model</p>
          {selectedModel && !changingPrimary ? (
            <ModelSummary
              model={selectedModel}
              credential={selectedCredential}
              onChange={() => setChangingPrimary(true)}
              onRemove={handleRemovePrimaryModel}
            />
          ) : activeModels.length > 0 ? (
            <div className="space-y-2">
              <Select
                value={state.providerModelId || ''}
                onChange={(event) => handleSelectPrimaryModel(event.target.value)}
                options={selectOptions}
              />
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="outline" onClick={goToModelsPage}>
                  <Boxes className="mr-2 h-4 w-4" />
                  Manage models
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setShowAddCredential(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add credential
                </Button>
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-background p-3">
              <p className="mb-3 text-sm text-muted">No reusable models are configured for this project yet.</p>
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="outline" onClick={goToModelsPage}>
                  <Boxes className="mr-2 h-4 w-4" />
                  Create model
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setShowAddCredential(true)}>
                  <Key className="mr-2 h-4 w-4" />
                  Add credential
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="space-y-3 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Generation Settings</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">Temperature</label>
              <Input
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={state.temperature}
                onChange={(event) => setField('temperature', parseFloat(event.target.value))}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">Max Output Tokens</label>
              <Input
                type="number"
                step="1"
                min="1"
                value={state.maxOutputTokens}
                onChange={(event) => setField('maxOutputTokens', parseInt(event.target.value))}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="space-y-3 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Fallback</p>
          <p className="text-xs text-muted">When the primary model fails, the system will retry using this fallback model.</p>

          {fallbackModel && !changingFallback ? (
            <ModelSummary
              model={fallbackModel}
              credential={fallbackCredential}
              onChange={() => setChangingFallback(true)}
              onRemove={handleRemoveFallbackModel}
            />
          ) : (
            <div className="space-y-2">
              <Select
                value={state.fallbackProviderModelId || ''}
                onChange={(event) => handleSelectFallbackModel(event.target.value)}
                options={[{ value: '', label: 'None (no fallback)' }, ...selectOptions.filter((item) => item.value)]}
              />
              {activeModels.length === 0 && (
                <Button type="button" size="sm" variant="outline" onClick={goToModelsPage}>
                  <Boxes className="mr-2 h-4 w-4" />
                  Create model
                </Button>
              )}
            </div>
          )}
        </div>
      </div>

      <AddProviderCredentialModal
        open={showAddCredential}
        onClose={() => setShowAddCredential(false)}
        projectId={projectId}
        onCredentialCreated={handleCredentialCreated}
      />
    </div>
  )
}
