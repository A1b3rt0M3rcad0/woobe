import { useState, useEffect } from 'react'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { useAgentEditor } from '../AgentEditorContext'
import type { ProviderCredential } from '@/features/provider-credentials/types'

const modelOptions: Record<string, { value: string; label: string }[]> = {
  openai: [
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    { value: 'gpt-4.1', label: 'GPT-4.1' },
  ],
  anthropic: [
    { value: 'claude-3-5-sonnet-latest', label: 'Claude 3.5 Sonnet' },
    { value: 'claude-3-5-haiku-latest', label: 'Claude 3.5 Haiku' },
    { value: 'claude-3-opus-latest', label: 'Claude 3 Opus' },
  ],
  google: [
    { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
    { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
    { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
  ],
}

const defaultModels: Record<string, string> = {
  openai: 'gpt-4o-mini',
  anthropic: 'claude-3-5-haiku-latest',
  google: 'gemini-1.5-flash',
}

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google',
  custom: 'Custom',
}

function getCredentialModel(credential: ProviderCredential): string {
  return credential.metadata?.model || credential.metadata?.model_name || ''
}

function getCredentialBaseUrl(credential: ProviderCredential): string {
  return credential.metadata?.base_url || ''
}

interface ModelSettingsTabProps {
  projectId: string
}

export function ModelSettingsTab({ projectId }: ModelSettingsTabProps) {
  const { data: credentials = [], refetch: refetchCredentials } = useCredentials(projectId)
  const { state, setField } = useAgentEditor()

  const [selectedCredential, setSelectedCredential] = useState<ProviderCredential | null>(null)
  const [showAddCredential, setShowAddCredential] = useState(false)
  const [fallbackProvider, setFallbackProvider] = useState('')
  const [fallbackModel, setFallbackModel] = useState('')
  const [fallbackCredentialId, setFallbackCredentialId] = useState('')

  useEffect(() => {
    const cred = credentials.find(c => c.id === state.providerCredentialId) || null
    setSelectedCredential(cred)
  }, [state.providerCredentialId, credentials])

  const handleSelectCredential = (id: string) => {
    const cred = credentials.find(c => c.id === id)
    if (cred) {
      setSelectedCredential(cred)
      setField('providerCredentialId', cred.id)
    }
  }

  const handleChangeCredential = () => setShowAddCredential(true)

  const handleRemoveCredential = () => {
    setSelectedCredential(null)
    setField('providerCredentialId', null)
    setField('provider', '')
    setField('model', '')
  }

  const handleCredentialCreated = async (newId: string) => {
    setShowAddCredential(false)
    await refetchCredentials()
    const match = credentials.find(c => c.id === newId)
    if (match) {
      setSelectedCredential(match)
      setField('providerCredentialId', match.id)
    }
  }

  const isCustom = selectedCredential?.provider === 'custom'
  const isStandard = selectedCredential
    ? (selectedCredential.provider === 'openai' || selectedCredential.provider === 'anthropic' || selectedCredential.provider === 'google')
    : false
  const availableModels = isStandard ? (modelOptions[selectedCredential!.provider] || []) : []

  const customMissingModel = isCustom && !getCredentialModel(selectedCredential!)
  const customMissingBaseUrl = isCustom && !getCredentialBaseUrl(selectedCredential!)

  const hasEditorState = state.provider && state.model

  return (
    <div className="p-4 space-y-4">
      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">Model Credential</p>
          {selectedCredential ? (
            <div className="rounded-lg border border-border bg-background p-3 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{providerLabels[selectedCredential.provider] || selectedCredential.provider}</Badge>
                  <span className="text-sm font-medium">{selectedCredential.name}</span>
                </div>
                <Badge variant={selectedCredential.status === 'active' ? 'success' : 'secondary'}>
                  {selectedCredential.status || 'active'}
                </Badge>
              </div>
              {isCustom && (
                <div className="text-xs text-muted space-y-1">
                  {getCredentialModel(selectedCredential) ? (
                    <p>Model: <code className="bg-background px-1 rounded">{getCredentialModel(selectedCredential)}</code></p>
                  ) : (
                    <p className="text-red-400">Model not configured</p>
                  )}
                  {getCredentialBaseUrl(selectedCredential) ? (
                    <p>Base URL: <code className="bg-background px-1 rounded">{getCredentialBaseUrl(selectedCredential)}</code></p>
                  ) : (
                    <p className="text-red-400">Base URL not configured</p>
                  )}
                </div>
              )}
              <div className="flex gap-2">
                <Button type="button" size="sm" variant="outline" onClick={handleChangeCredential}>Change</Button>
                <Button type="button" size="sm" variant="ghost" onClick={handleRemoveCredential}>Remove</Button>
              </div>
            </div>
          ) : state.providerCredentialId && hasEditorState ? (
            <div className="rounded-lg border border-border bg-background p-3 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{providerLabels[state.provider] || state.provider}</Badge>
                  <span className="text-sm font-medium">{state.provider}/{state.model}</span>
                </div>
                <Badge variant="secondary">configured</Badge>
              </div>
              <div className="text-xs text-muted space-y-1">
                <p>Provider: <code className="bg-background px-1 rounded">{state.provider}</code></p>
                <p>Model: <code className="bg-background px-1 rounded">{state.model}</code></p>
                {state.baseUrl && <p>Base URL: <code className="bg-background px-1 rounded">{state.baseUrl}</code></p>}
              </div>
              <div className="flex gap-2">
                <Button type="button" size="sm" variant="outline" onClick={handleChangeCredential}>Change</Button>
                <Button type="button" size="sm" variant="ghost" onClick={handleRemoveCredential}>Remove</Button>
              </div>
            </div>
          ) : credentials.length > 0 ? (
            <div className="space-y-2">
              <Select
                value=""
                onChange={(e) => handleSelectCredential(e.target.value)}
                options={[
                  { value: '', label: 'Select a credential' },
                  ...credentials.map(c => ({
                    value: c.id,
                    label: `${c.name} (${providerLabels[c.provider] || c.provider})`,
                  })),
                ]}
              />
              <Button type="button" size="sm" variant="outline" onClick={() => setShowAddCredential(true)}>
                Add credential
              </Button>
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-background p-3">
              <p className="text-sm text-muted mb-2">No provider credential available. Add an API key to connect this agent to a model provider.</p>
              <Button type="button" size="sm" variant="outline" onClick={() => setShowAddCredential(true)}>
                Add credential
              </Button>
            </div>
          )}
        </div>
      </div>

      {selectedCredential && (customMissingModel || customMissingBaseUrl) && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3">
          <p className="text-sm text-red-400">
            {customMissingModel && 'This custom credential is missing a model. '}
            {customMissingBaseUrl && 'This custom credential is missing a base URL. '}
            Recreate the credential with the required fields.
          </p>
        </div>
      )}

      {selectedCredential && isStandard && (
        <div className="rounded-xl border border-border bg-surface">
          <div className="p-4 space-y-3">
            <p className="text-xs font-semibold text-muted uppercase tracking-wider">Model</p>
            <Select value={state.model} onChange={(e) => setField('model', e.target.value)} options={availableModels} />
          </div>
        </div>
      )}

      {selectedCredential && isCustom && (
        <div className="rounded-xl border border-border bg-surface">
          <div className="p-4 space-y-3">
            <p className="text-xs font-semibold text-muted uppercase tracking-wider">Model</p>
            <div className="rounded-lg border border-border bg-background p-3">
              <p className="text-xs text-muted mb-2">Model is defined by the credential.</p>
              <p className="text-sm">Selected: <code className="bg-background px-1 rounded">{state.model || getCredentialModel(selectedCredential)}</code></p>
            </div>
          </div>
        </div>
      )}

      {!selectedCredential && hasEditorState && (
        <div className="rounded-xl border border-border bg-surface">
          <div className="p-4 space-y-3">
            <p className="text-xs font-semibold text-muted uppercase tracking-wider">Model</p>
            <div className="rounded-lg border border-border bg-background p-3">
              <p className="text-sm">Selected: <code className="bg-background px-1 rounded">{state.provider}/{state.model}</code></p>
            </div>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">Generation Settings</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-muted mb-1">Temperature</label>
              <Input
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={state.temperature}
                onChange={(e) => setField('temperature', parseFloat(e.target.value))}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted mb-1">Max Output Tokens</label>
              <Input
                type="number"
                step="1"
                min="1"
                value={state.maxOutputTokens}
                onChange={(e) => setField('maxOutputTokens', parseInt(e.target.value))}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">Fallback</p>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Fallback Provider</label>
            <Select
              value={fallbackProvider}
              onChange={(e) => setFallbackProvider(e.target.value)}
              options={[
                { value: '', label: 'None' },
                { value: 'openai', label: 'OpenAI' },
                { value: 'anthropic', label: 'Anthropic' },
                { value: 'google', label: 'Google' },
              ]}
            />
          </div>
          {fallbackProvider === 'openai' && (
            <div>
              <label className="block text-xs font-medium text-muted mb-1">Fallback Model</label>
              <Select
                value={fallbackModel}
                onChange={(e) => setFallbackModel(e.target.value)}
                options={[
                  { value: '', label: 'None' },
                  ...modelOptions.openai,
                ]}
              />
            </div>
          )}
          {fallbackProvider === 'anthropic' && (
            <div>
              <label className="block text-xs font-medium text-muted mb-1">Fallback Model</label>
              <Select
                value={fallbackModel}
                onChange={(e) => setFallbackModel(e.target.value)}
                options={[
                  { value: '', label: 'None' },
                  ...modelOptions.anthropic,
                ]}
              />
            </div>
          )}
          {fallbackProvider === 'google' && (
            <div>
              <label className="block text-xs font-medium text-muted mb-1">Fallback Model</label>
              <Select
                value={fallbackModel}
                onChange={(e) => setFallbackModel(e.target.value)}
                options={[
                  { value: '', label: 'None' },
                  ...modelOptions.google,
                ]}
              />
            </div>
          )}
        </div>
      </div>

      <AddProviderCredentialModal
        open={showAddCredential}
        onClose={() => setShowAddCredential(false)}
        projectId={projectId}
        credential={selectedCredential}
        onCredentialCreated={handleCredentialCreated}
      />
    </div>
  )
}
