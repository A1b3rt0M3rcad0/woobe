import { AgentBehaviorFields } from '@/features/agents/components/AgentBehaviorSettings'
import { behaviorFromSpec, behaviorToSpec } from '@/features/agents/behavior'
import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useAgent, useUpdateAgent } from '@/features/agents/hooks'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { createAgentSchema, type CreateAgentFormData } from '@/features/agents/schemas'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { workspaceProjectPath } from '@/lib/constants/routes'
import { toast } from 'sonner'
import { ArrowLeft } from 'lucide-react'
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

const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
]

function getCredentialModel(credential: ProviderCredential): string {
  return credential.metadata?.model || credential.metadata?.model_name || ''
}

function getCredentialBaseUrl(credential: ProviderCredential): string {
  return credential.metadata?.base_url || ''
}

export default function EditAgentPage() {
  const { workspaceId, projectId, agentId } = useParams<{ workspaceId?: string; projectId: string; agentId: string }>()
  const navigate = useNavigate()
  const { data: agent, isLoading, isError, error } = useAgent(agentId)
  const updateAgent = useUpdateAgent(agentId)
  const { data: credentials = [], refetch: refetchCredentials } = useCredentials(projectId)
  const [showAddCredential, setShowAddCredential] = useState(false)
  const [selectedCredential, setSelectedCredential] = useState<ProviderCredential | null>(null)
  const [behavior, setBehavior] = useState(() => behaviorFromSpec())
  const [formReady, setFormReady] = useState(false)
  const pendingCredentialId = useRef<string | null>(null)

  const p = (projId: string, ...segments: string[]) => workspaceProjectPath(workspaceId, projId, ...segments)

  const form = useForm<CreateAgentFormData>({
    resolver: zodResolver(createAgentSchema),
  })

  useEffect(() => {
    if (!agent || !credentials.length || formReady) return
    const cred = credentials.find(c => c.id === agent.provider_credential_id) || null
    setSelectedCredential(cred)
    form.reset({
      name: agent.name,
      description: agent.description || '',
      provider: agent.provider,
      model: agent.model,
      temperature: agent.temperature ?? 0.7,
      max_output_tokens: agent.max_output_tokens ?? 2048,
      provider_credential_id: agent.provider_credential_id || '',
      session_mode: (agent.session_mode === 'stateless' ? 'stateless' : 'stateful') as 'stateful' | 'stateless',
      status: agent.status === 'active' ? 'active' : 'inactive',
    })
    setBehavior(behaviorFromSpec(agent.behavior_spec, agent.system_prompt))
    setFormReady(true)
  }, [agent, credentials, form, formReady])

  const selectedProvider = selectedCredential?.provider || agent?.provider || ''
  const isCustom = selectedProvider === 'custom'
  const isStandard = selectedProvider === 'openai' || selectedProvider === 'anthropic' || selectedProvider === 'google'
  const availableModels = isStandard ? (modelOptions[selectedProvider] || []) : []

  useEffect(() => {
    if (!selectedCredential) return
    const provider = selectedCredential.provider
    form.setValue('provider', provider)
    form.setValue('provider_credential_id', selectedCredential.id)
    if (provider === 'custom') {
      form.setValue('model', getCredentialModel(selectedCredential))
    } else {
      form.setValue('model', defaultModels[provider] || '')
    }
  }, [selectedCredential, form])

  const handleCredentialCreated = async (newId: string) => {
    setShowAddCredential(false)
    pendingCredentialId.current = newId
    await refetchCredentials()
  }

  useEffect(() => {
    if (pendingCredentialId.current) {
      const match = credentials.find(c => c.id === pendingCredentialId.current)
      if (match) {
        setSelectedCredential(match)
        pendingCredentialId.current = null
        return
      }
    }
    if (!selectedCredential) return
    const match = credentials.find(c => c.id === selectedCredential.id)
    if (match) {
      setSelectedCredential(match)
    }
  }, [credentials])

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
    form.setValue('provider_credential_id', '')
    form.setValue('provider', '')
    form.setValue('model', '')
  }

  const onSubmit = async (data: CreateAgentFormData) => {
    if (!selectedCredential) {
      toast.error('Select a provider credential first')
      return
    }
    try {
      const model = isCustom
        ? getCredentialModel(selectedCredential)
        : data.model

      const payload: Record<string, unknown> = {
        name: data.name,
        provider: selectedCredential.provider,
        model,
        behavior_spec: behaviorToSpec(behavior),
        description: data.description || '',
        temperature: data.temperature,
        max_output_tokens: data.max_output_tokens,
        provider_credential_id: selectedCredential.id,
        session_mode: data.session_mode || 'stateful',
        status: data.status,
      }
      if (isCustom) {
        const baseUrl = getCredentialBaseUrl(selectedCredential)
        if (baseUrl) {
          payload.settings = { base_url: baseUrl }
        }
      }
      await updateAgent.mutateAsync(payload as any)
      toast.success('Agent updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update agent')
    }
  }

  const nameValue = form.watch('name')

  const disabledReason = () => {
    if (!selectedCredential) return 'Select a provider credential to continue.'
    if (!nameValue) return 'Agent name is required.'
    if (!projectId) return 'Project ID is missing.'
    if (isCustom && selectedCredential) {
      if (!getCredentialModel(selectedCredential)) return 'Custom credentials require a model in their metadata.'
      if (!getCredentialBaseUrl(selectedCredential)) return 'Custom credentials require a base URL.'
    }
    if (isStandard && !form.watch('model')) return 'Select a model to continue.'
    return null
  }

  const reason = disabledReason()
  const customMissingModel = isCustom && selectedCredential && !getCredentialModel(selectedCredential)
  const customMissingBaseUrl = isCustom && selectedCredential && !getCredentialBaseUrl(selectedCredential)

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={() => navigate(p(projectId!, 'agents'))} />
  if (!agent) return <ErrorState message="Agent not found" />

  return (
    <div>
      <PageHeader
        title="Edit Agent"
        description={`Update configuration for ${agent.name}`}
        actions={
          <Button variant="ghost" size="sm" onClick={() => navigate(p(projectId!, 'agents', agentId!, 'playground'))}>
            <ArrowLeft className="mr-1 h-4 w-4" />
            Back to Playground
          </Button>
        }
      />

      <Card className="max-w-2xl">
        <CardContent className="p-6">
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
            <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
              <p className="text-xs font-semibold text-muted uppercase tracking-wider">Agent Details</p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-muted mb-1">Name</label>
                  <Input {...form.register('name')} error={form.formState.errors.name?.message} placeholder="My Agent" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted mb-1">Status</label>
                  <Select {...form.register('status')} options={statusOptions} />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted mb-1">Description</label>
                <Input {...form.register('description')} placeholder="Optional description" />
              </div>
            </div>

            <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
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
                  <p className="text-xs text-muted mb-2">No provider credential available. Add an API key to connect this agent to a model provider.</p>
                  <Button type="button" size="sm" variant="outline" onClick={() => setShowAddCredential(true)}>
                    Add credential
                  </Button>
                </div>
              )}
            </div>

            {selectedCredential && customMissingModel && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3">
                <p className="text-xs text-red-400">This custom credential is missing a model. Recreate the credential with a model name.</p>
              </div>
            )}

            {selectedCredential && customMissingBaseUrl && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3">
                <p className="text-xs text-red-400">This custom credential is missing a base URL. Recreate the credential with a base URL.</p>
              </div>
            )}

            {isStandard && (
              <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
                <p className="text-xs font-semibold text-muted uppercase tracking-wider">Model</p>
                <Select value={form.watch('model')} onChange={(e) => form.setValue('model', e.target.value)} options={availableModels} />
              </div>
            )}

            <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
              <p className="text-xs font-semibold text-muted uppercase tracking-wider">Generation Settings</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-muted mb-1">Session Mode</label>
                  <Select
                    {...form.register('session_mode')}
                    options={[
                      { value: 'stateful', label: 'Stateful' },
                      { value: 'stateless', label: 'Stateless' },
                    ]}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted mb-1">Temperature</label>
                  <Input type="number" step="0.1" min="0" max="2" {...form.register('temperature')} />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted mb-1">Max Output Tokens</label>
                <Input type="number" step="1" min="1" {...form.register('max_output_tokens')} />
              </div>
            </div>

            <AgentBehaviorFields behavior={behavior} onChange={setBehavior} />

            <div className="flex flex-col items-end gap-1">
              {reason && (
                <p className="text-xs text-muted">{reason}</p>
              )}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => navigate(p(projectId!, 'agents', agentId!, 'playground'))}>Back</Button>
                <Button type="submit" loading={updateAgent.isPending} disabled={!!reason}>
                  Save Changes
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      <AddProviderCredentialModal
        open={showAddCredential}
        onClose={() => setShowAddCredential(false)}
        projectId={projectId!}
        credential={selectedCredential}
        onCredentialCreated={handleCredentialCreated}
      />
    </div>
  )
}
