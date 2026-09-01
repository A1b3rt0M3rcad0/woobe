import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useCreateAgent } from '@/features/agents/hooks'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { createAgentSchema, type CreateAgentFormData } from '@/features/agents/schemas'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { JsonEditor } from '@/components/ui/JsonEditor'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { Separator } from '@/components/ui/Separator'
import { ChevronDown, ChevronRight, FileJson } from 'lucide-react'
import { workspaceProjectPath } from '@/lib/constants/routes'
import { toast } from 'sonner'
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

export default function CreateAgentPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId?: string; projectId: string }>()
  const navigate = useNavigate()
  const createAgent = useCreateAgent(projectId)
  const { data: credentials = [], refetch: refetchCredentials } = useCredentials(projectId)
  const [showAddCredential, setShowAddCredential] = useState(false)
  const [selectedCredential, setSelectedCredential] = useState<ProviderCredential | null>(null)
  const [showAdvancedOutput, setShowAdvancedOutput] = useState(false)
  const [outputEnabled, setOutputEnabled] = useState(false)
  const [outputSchema, setOutputSchema] = useState(`{\n  "type": "object",\n  "properties": {\n    "category": {\n      "type": "string",\n      "enum": ["support", "sales", "bug", "other"]\n    },\n    "summary": {\n      "type": "string"\n    },\n    "confidence": {\n      "type": "number"\n    }\n  },\n  "required": ["category", "summary"]\n}`)
  const [outputStrict, setOutputStrict] = useState(false)
  const [outputSchemaError, setOutputSchemaError] = useState<string | null>(null)
  const pendingCredentialId = useRef<string | null>(null)

  const p = (projId: string, ...segments: string[]) => workspaceProjectPath(workspaceId, projId, ...segments)

  const form = useForm<CreateAgentFormData>({
    resolver: zodResolver(createAgentSchema),
    defaultValues: {
      temperature: 0.7,
      max_output_tokens: 2048,
      session_mode: 'stateful',
    },
  })

  const selectedProvider = selectedCredential?.provider || ''
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

      const payloadSettings: Record<string, unknown> = {}

      if (isCustom) {
        const baseUrl = getCredentialBaseUrl(selectedCredential)
        if (baseUrl) {
          payloadSettings.base_url = baseUrl
        }
      }

      if (outputEnabled) {
        let parsedSchema: unknown = null
        try {
          parsedSchema = outputSchema ? JSON.parse(outputSchema) : null
        } catch {
          setOutputSchemaError('Invalid JSON schema')
          return
        }
        payloadSettings.response_format = {
          enabled: true,
          type: 'json',
          schema: parsedSchema,
          strict: outputStrict,
        }
      }

      const payload: Record<string, unknown> = {
        project_id: projectId!,
        name: data.name,
        provider: selectedCredential.provider,
        model,
        system_prompt: data.system_prompt || '',
        description: data.description || '',
        temperature: data.temperature,
        max_output_tokens: data.max_output_tokens,
        provider_credential_id: selectedCredential.id,
        session_mode: data.session_mode || 'stateful',
        settings: Object.keys(payloadSettings).length > 0 ? payloadSettings : undefined,
      }
      const agent = await createAgent.mutateAsync(payload as any)
      toast.success('Agent created')
      navigate(p(projectId!, 'agents', agent.id, 'playground'))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create agent')
    }
  }

  const nameValue = form.watch('name')

  const disabledReason = () => {
    if (!selectedCredential) return 'Add a provider credential to continue.'
    if (!nameValue) return 'Agent name is required.'
    if (!projectId) return 'Project ID is missing.'
    if (isCustom) {
      if (!getCredentialModel(selectedCredential!)) return 'Custom credentials require a model in their metadata.'
      if (!getCredentialBaseUrl(selectedCredential!)) return 'Custom credentials require a base URL.'
    }
    if (isStandard && !form.watch('model')) return 'Select a model to continue.'
    return null
  }

  const reason = disabledReason()
  const customMissingModel = isCustom && !getCredentialModel(selectedCredential!)
  const customMissingBaseUrl = isCustom && !getCredentialBaseUrl(selectedCredential!)

  return (
    <div>
      <PageHeader
        title="Create Agent"
        description="Configure a new AI agent"
      />

      <Card className="max-w-2xl">
        <CardContent className="p-6">
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-muted mb-1">Name</label>
              <Input {...form.register('name')} error={form.formState.errors.name?.message} placeholder="My Agent" />
            </div>
            <div>
              <label className="block text-sm font-medium text-muted mb-1">Description</label>
              <Input {...form.register('description')} placeholder="Optional description" />
            </div>

            <div className="border-t border-border pt-4">
              <p className="text-sm font-semibold mb-3">Model Credential</p>
              {selectedCredential ? (
                <div className="rounded-lg border border-border bg-background p-4 space-y-3">
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
                <div className="space-y-3">
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
                <div className="rounded-lg border border-border bg-background p-4">
                  <p className="text-sm text-muted mb-3">No provider credential selected. Add an API key to connect this agent to a model provider.</p>
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

            {isStandard && (
              <div>
                <label className="block text-sm font-medium text-muted mb-1">Model</label>
                <Select {...form.register('model')} options={availableModels} />
              </div>
            )}

            <div className="border-t border-border pt-4">
              <p className="text-sm font-semibold mb-3">Runtime</p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-muted mb-1">Session Mode</label>
                  <Select
                    {...form.register('session_mode')}
                    options={[
                      { value: 'stateful', label: 'Stateful conversation' },
                      { value: 'stateless', label: 'Stateless request' },
                    ]}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-muted mb-1">Temperature</label>
                  <Input type="number" step="0.1" min="0" max="2" {...form.register('temperature')} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 mt-3">
                <div>
                  <label className="block text-sm font-medium text-muted mb-1">Max Output Tokens</label>
                  <Input type="number" step="1" min="1" {...form.register('max_output_tokens')} />
                </div>
              </div>
            </div>

            <div className="border-t border-border pt-4">
              <p className="text-sm font-semibold mb-3">Prompt</p>
              <div>
                <label className="block text-sm font-medium text-muted mb-1">System Prompt</label>
                <Textarea
                  {...form.register('system_prompt')}
                  placeholder="You are a helpful AI assistant..."
                  className="min-h-[120px]"
                />
              </div>
            </div>

            <div className="border-t border-border pt-4">
              <button
                type="button"
                onClick={() => setShowAdvancedOutput(!showAdvancedOutput)}
                className="flex items-center gap-2 text-sm font-semibold text-muted hover:text-white transition-colors"
              >
                {showAdvancedOutput ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                <FileJson className="h-4 w-4" />
                Advanced API Output
              </button>

              {showAdvancedOutput && (
                <div className="mt-3 space-y-3 pl-6">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="create-output-enabled"
                      checked={outputEnabled}
                      onChange={(e) => {
                        setOutputEnabled(e.target.checked)
                        if (!e.target.checked) setOutputSchemaError(null)
                      }}
                      className="h-4 w-4 rounded border-border bg-background"
                    />
                    <label htmlFor="create-output-enabled" className="text-sm font-medium text-muted">
                      Enable JSON output
                    </label>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-muted mb-1">
                      JSON Schema
                    </label>
                    <JsonEditor
                      value={outputSchema}
                      onChange={(val) => {
                        setOutputSchema(val)
                        if (outputSchemaError) {
                          try { JSON.parse(val); setOutputSchemaError(null) } catch { }
                        }
                      }}
                      editable
                      disabled={!outputEnabled}
                      actions={['format', 'validate', 'clear']}
                      minHeight={150}
                      placeholder='{ "type": "object", ... }'
                      error={outputSchemaError}
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="create-output-strict"
                      checked={outputStrict}
                      onChange={(e) => setOutputStrict(e.target.checked)}
                      disabled={!outputEnabled}
                      className="h-4 w-4 rounded border-border bg-background"
                    />
                    <label htmlFor="create-output-strict" className="text-sm font-medium text-muted">
                      Strict mode
                    </label>
                  </div>
                </div>
              )}
            </div>

            <div className="flex flex-col items-end gap-1">
              {reason && (
                <p className="text-xs text-muted">{reason}</p>
              )}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => navigate(-1)}>Cancel</Button>
                <Button type="submit" loading={createAgent.isPending} disabled={!!reason}>
                  Create Agent
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
        onCredentialCreated={handleCredentialCreated}
      />
    </div>
  )
}
