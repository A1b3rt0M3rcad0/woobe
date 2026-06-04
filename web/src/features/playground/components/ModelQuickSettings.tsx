import { useState, useEffect } from 'react'
import { useUpdateAgent } from '@/features/agents/hooks'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { toast } from 'sonner'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import type { Agent } from '@/features/agents/types'
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

interface ModelQuickSettingsProps {
  agent: Agent
  projectId: string
}

export function ModelQuickSettings({ agent, projectId }: ModelQuickSettingsProps) {
  const updateAgent = useUpdateAgent(agent.id)
  const { data: credentials = [], refetch: refetchCredentials } = useCredentials(projectId)

  const [selectedCredential, setSelectedCredential] = useState<ProviderCredential | null>(null)
  const [provider, setProvider] = useState(agent.provider)
  const [model, setModel] = useState(agent.model)
  const [temperature, setTemperature] = useState(agent.temperature ?? 0.7)
  const [maxTokens, setMaxTokens] = useState(agent.max_output_tokens ?? 2048)
  const [showAddCredential, setShowAddCredential] = useState(false)
  const [fallbackProvider, setFallbackProvider] = useState(agent.fallback_provider || '')
  const [fallbackModel, setFallbackModel] = useState(agent.fallback_model || '')
  const [fallbackCredentialId, setFallbackCredentialId] = useState(agent.fallback_credential_id || '')

  useEffect(() => {
    const cred = credentials.find(c => c.id === agent.provider_credential_id) || null
    setSelectedCredential(cred)
    setProvider(agent.provider)
    setModel(agent.model)
    setTemperature(agent.temperature ?? 0.7)
    setMaxTokens(agent.max_output_tokens ?? 2048)
    setFallbackProvider(agent.fallback_provider || '')
    setFallbackModel(agent.fallback_model || '')
    setFallbackCredentialId(agent.fallback_credential_id || '')
  }, [agent, credentials])

  const isCustom = selectedCredential?.provider === 'custom'
  const isStandard = selectedCredential
    ? (selectedCredential.provider === 'openai' || selectedCredential.provider === 'anthropic' || selectedCredential.provider === 'google')
    : false
  const availableModels = isStandard ? (modelOptions[selectedCredential!.provider] || []) : []

  useEffect(() => {
    if (!selectedCredential) return
    const p = selectedCredential.provider
    setProvider(p)
    if (p === 'custom') {
      setModel(getCredentialModel(selectedCredential))
    } else {
      const defaultM = defaultModels[p]
      if (defaultM && !availableModels.find(m => m.value === model)) {
        setModel(defaultM)
      }
    }
  }, [selectedCredential])

  const handleSelectCredential = (id: string) => {
    const cred = credentials.find(c => c.id === id)
    if (cred) {
      setSelectedCredential(cred)
    }
  }

  const handleChangeCredential = () => {
    setShowAddCredential(true)
  }

  const handleRemoveCredential = () => {
    setSelectedCredential(null)
    setProvider('')
    setModel('')
  }

  const handleCredentialCreated = async (newId: string) => {
    setShowAddCredential(false)
    await refetchCredentials()
    const match = credentials.find(c => c.id === newId)
    if (match) {
      setSelectedCredential(match)
    }
  }

  const hasChanges =
    provider !== agent.provider ||
    model !== agent.model ||
    (selectedCredential?.id || '') !== (agent.provider_credential_id || '') ||
    temperature !== (agent.temperature ?? 0.7) ||
    maxTokens !== (agent.max_output_tokens ?? 2048) ||
    fallbackProvider !== (agent.fallback_provider || '') ||
    fallbackModel !== (agent.fallback_model || '') ||
    fallbackCredentialId !== (agent.fallback_credential_id || '')

  const handleSave = async () => {
    try {
      const payload: Record<string, unknown> = {}
      if (provider !== agent.provider) payload.provider = provider
      if (model !== agent.model) payload.model = model
      const credId = (selectedCredential?.id || '') || null
      const origCred = agent.provider_credential_id || ''
      if (credId !== origCred) payload.provider_credential_id = credId || null
      const origTemp = agent.temperature ?? 0.7
      if (temperature !== origTemp) payload.temperature = temperature
      const origTokens = agent.max_output_tokens ?? 2048
      if (maxTokens !== origTokens) payload.max_output_tokens = maxTokens
      const origFbProv = agent.fallback_provider || ''
      if (fallbackProvider !== origFbProv) payload.fallback_provider = fallbackProvider || null
      const origFbModel = agent.fallback_model || ''
      if (fallbackModel !== origFbModel) payload.fallback_model = fallbackModel || null
      const origFbCred = agent.fallback_credential_id || ''
      if (fallbackCredentialId !== origFbCred) payload.fallback_credential_id = fallbackCredentialId || null
      await updateAgent.mutateAsync(payload as any)
      toast.success('Model updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update model')
    }
  }

  const customMissingModel = isCustom && !getCredentialModel(selectedCredential!)
  const customMissingBaseUrl = isCustom && !getCredentialBaseUrl(selectedCredential!)

  return (
    <>
      <Card>
        <CardContent className="p-4 space-y-4">
          <div>
            <p className="text-xs font-medium text-muted mb-2">Model Credential</p>
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
                  <Button type="button" size="sm" variant="outline" onClick={handleChangeCredential}>
                    Change
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={handleRemoveCredential}>
                    Remove
                  </Button>
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

          {selectedCredential && customMissingModel && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3">
              <p className="text-sm text-red-400">This custom credential is missing a model. Recreate the credential with a model name.</p>
            </div>
          )}

          {selectedCredential && customMissingBaseUrl && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3">
              <p className="text-sm text-red-400">This custom credential is missing a base URL. Recreate the credential with a base URL.</p>
            </div>
          )}

          {selectedCredential && isStandard && (
            <div>
              <label className="block text-sm font-medium text-muted mb-1">Model</label>
              <Select value={model} onChange={(e) => setModel(e.target.value)} options={availableModels} />
            </div>
          )}

          {selectedCredential && isCustom && (
            <div>
              <label className="block text-sm font-medium text-muted mb-1">Model</label>
              <div className="rounded-lg border border-border bg-background p-3">
                <p className="text-xs text-muted mb-2">Model is defined by the credential.</p>
                <p className="text-sm">Selected: <code className="bg-background px-1 rounded">{model || getCredentialModel(selectedCredential)}</code></p>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-muted mb-1">Temperature</label>
              <Input
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-muted mb-1">Max Output Tokens</label>
              <Input
                type="number"
                step="1"
                min="1"
                value={maxTokens}
                onChange={(e) => setMaxTokens(parseInt(e.target.value))}
              />
            </div>
          </div>

          <div className="border-t border-border pt-3">
            <p className="text-xs font-medium text-muted mb-2">Fallback Configuration</p>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label className="block text-sm font-medium text-muted mb-1">Fallback Provider</label>
                <Select
                  value={fallbackProvider}
                  onChange={(e) => setFallbackProvider(e.target.value)}
                  options={[
                    { value: '', label: 'None' },
                    { value: 'openai', label: 'OpenAI' },
                    { value: 'anthropic', label: 'Anthropic' },
                    { value: 'google', label: 'Google' },
                    { value: 'azure', label: 'Azure' },
                    { value: 'custom', label: 'Custom' },
                  ]}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted mb-1">Fallback Model</label>
                <Input value={fallbackModel} onChange={(e) => setFallbackModel(e.target.value)} placeholder="Optional" />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted mb-1">Fallback Credential</label>
              <Select
                value={fallbackCredentialId}
                onChange={(e) => setFallbackCredentialId(e.target.value)}
                options={[
                  { value: '', label: 'None' },
                  ...credentials.map(c => ({
                    value: c.id,
                    label: `${c.name} (${providerLabels[c.provider] || c.provider})`,
                  })),
                ]}
              />
            </div>
          </div>

          <div className="flex gap-2 pt-1">
            <Button size="sm" onClick={handleSave} disabled={!hasChanges} loading={updateAgent.isPending}>
              Save Changes
            </Button>
          </div>
        </CardContent>
      </Card>

      <AddProviderCredentialModal
        open={showAddCredential}
        onClose={() => setShowAddCredential(false)}
        projectId={projectId}
        credential={selectedCredential}
        onCredentialCreated={handleCredentialCreated}
      />
    </>
  )
}
