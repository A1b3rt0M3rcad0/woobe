import { useState, useEffect } from 'react'
import { useUpdateAgent } from '@/features/agents/hooks'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { toast } from 'sonner'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import type { Agent } from '@/features/agents/types'

const providers = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google' },
  { value: 'azure', label: 'Azure' },
  { value: 'custom', label: 'Custom' },
]

const modelsByProvider: Record<string, { value: string; label: string }[]> = {
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
  azure: [
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'gpt-4o', label: 'GPT-4o' },
  ],
}

interface ModelQuickSettingsProps {
  agent: Agent
  projectId: string
}

export function ModelQuickSettings({ agent, projectId }: ModelQuickSettingsProps) {
  const updateAgent = useUpdateAgent(agent.id)
  const { data: credentials } = useCredentials(projectId)

  const [provider, setProvider] = useState(agent.provider)
  const [model, setModel] = useState(agent.model)
  const [credentialId, setCredentialId] = useState(agent.provider_credential_id || '')
  const [temperature, setTemperature] = useState(agent.temperature ?? 0.7)
  const [maxTokens, setMaxTokens] = useState(agent.max_output_tokens ?? 2048)
  const [showAddCredential, setShowAddCredential] = useState(false)
  const [fallbackProvider, setFallbackProvider] = useState(agent.fallback_provider || '')
  const [fallbackModel, setFallbackModel] = useState(agent.fallback_model || '')
  const [fallbackCredentialId, setFallbackCredentialId] = useState(agent.fallback_credential_id || '')

  useEffect(() => {
    setProvider(agent.provider)
    setModel(agent.model)
    setCredentialId(agent.provider_credential_id || '')
    setTemperature(agent.temperature ?? 0.7)
    setMaxTokens(agent.max_output_tokens ?? 2048)
    setFallbackProvider(agent.fallback_provider || '')
    setFallbackModel(agent.fallback_model || '')
    setFallbackCredentialId(agent.fallback_credential_id || '')
  }, [agent])

  const availableModels = modelsByProvider[provider] || modelsByProvider.openai

  const hasChanges =
    provider !== agent.provider ||
    model !== agent.model ||
    credentialId !== (agent.provider_credential_id || '') ||
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
      const origCred = agent.provider_credential_id || ''
      if (credentialId !== origCred) payload.provider_credential_id = credentialId || null
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

  const handleCredentialCreated = (newId: string) => {
    setCredentialId(newId)
  }

  const credentialOptions = (credentials || []).map((c) => ({
    value: c.id,
    label: `${c.name} (${c.provider})`,
  }))

  return (
    <>
      <Card>
        <CardContent className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-muted mb-1">Provider</label>
              <Select value={provider} onChange={(e) => setProvider(e.target.value)} options={providers} />
            </div>
            <div>
              <label className="block text-sm font-medium text-muted mb-1">Model</label>
              {provider === 'custom' ? (
                <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="e.g. my-model-name" />
              ) : (
                <Select value={model} onChange={(e) => setModel(e.target.value)} options={availableModels} />
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-muted mb-1">Credential</label>
            {credentialOptions.length === 0 ? (
              <div className="rounded-lg border border-border bg-background p-3">
                <p className="text-sm text-muted mb-2">No provider credential connected</p>
                <Button size="sm" variant="outline" onClick={() => setShowAddCredential(true)}>
                  Add credential
                </Button>
              </div>
            ) : (
              <div className="flex gap-2">
                <div className="flex-1">
                  <Select
                    value={credentialId}
                    onChange={(e) => setCredentialId(e.target.value)}
                    options={[{ value: '', label: 'No credential' }, ...credentialOptions]}
                  />
                </div>
                <Button size="sm" variant="outline" onClick={() => setShowAddCredential(true)}>
                  +
                </Button>
              </div>
            )}
          </div>

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
                <Select value={fallbackProvider} onChange={(e) => setFallbackProvider(e.target.value)} options={[{ value: '', label: 'None' }, ...providers]} />
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
                options={[{ value: '', label: 'None' }, ...credentialOptions]}
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
        onCredentialCreated={handleCredentialCreated}
      />
    </>
  )
}
