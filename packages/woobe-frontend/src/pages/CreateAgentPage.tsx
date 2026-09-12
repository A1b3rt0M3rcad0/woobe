import { behaviorFromSpec, behaviorToSpec } from '@/features/agents/behavior'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { ChevronDown, ChevronRight, FileJson } from 'lucide-react'
import { toast } from 'sonner'
import {
  Alert,
  AlertDescription,
  Checkbox,
  EmptyStatePanel,
  Field,
  FieldLabel,
  SectionBlock,
  TechnicalListItem,
} from '@woobe/ui'
import { useCreateAgent } from '@/features/agents/hooks'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { createAgentSchema, type CreateAgentFormData } from '@/features/agents/schemas'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { JsonEditor } from '@/components/ui/JsonEditor'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { workspaceProjectPath } from '@/lib/constants/routes'
import type { ProviderCredential } from '@/features/provider-credentials/types'

const modelOptions: Record<string, { value: string; label: string }[]> = {
  openai: [{ value: 'gpt-4o-mini', label: 'GPT-4o Mini' }, { value: 'gpt-4o', label: 'GPT-4o' }, { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' }, { value: 'gpt-4.1', label: 'GPT-4.1' }],
  anthropic: [{ value: 'claude-3-5-sonnet-latest', label: 'Claude 3.5 Sonnet' }, { value: 'claude-3-5-haiku-latest', label: 'Claude 3.5 Haiku' }, { value: 'claude-3-opus-latest', label: 'Claude 3 Opus' }],
  google: [{ value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' }, { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' }, { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' }],
}
const defaultModels: Record<string, string> = { openai: 'gpt-4o-mini', anthropic: 'claude-3-5-haiku-latest', google: 'gemini-1.5-flash' }
const providerLabels: Record<string, string> = { openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google', custom: 'Custom' }

function getCredentialModel(credential: ProviderCredential): string { return credential.metadata?.model || credential.metadata?.model_name || '' }
function getCredentialBaseUrl(credential: ProviderCredential): string { return credential.metadata?.base_url || '' }

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
  const form = useForm<CreateAgentFormData>({ resolver: zodResolver(createAgentSchema), defaultValues: { temperature: 0.7, max_output_tokens: 2048, session_mode: 'stateful' } })

  const selectedProvider = selectedCredential?.provider || ''
  const isCustom = selectedProvider === 'custom'
  const isStandard = selectedProvider === 'openai' || selectedProvider === 'anthropic' || selectedProvider === 'google'
  const availableModels = isStandard ? (modelOptions[selectedProvider] || []) : []

  useEffect(() => {
    if (!selectedCredential) return
    const provider = selectedCredential.provider
    form.setValue('provider', provider)
    form.setValue('provider_credential_id', selectedCredential.id)
    form.setValue('model', provider === 'custom' ? getCredentialModel(selectedCredential) : defaultModels[provider] || '')
  }, [selectedCredential, form])

  const handleCredentialCreated = async (newId: string) => { setShowAddCredential(false); pendingCredentialId.current = newId; await refetchCredentials() }
  useEffect(() => {
    if (pendingCredentialId.current) {
      const match = credentials.find(c => c.id === pendingCredentialId.current)
      if (match) { setSelectedCredential(match); pendingCredentialId.current = null; return }
    }
    if (!selectedCredential) return
    const match = credentials.find(c => c.id === selectedCredential.id)
    if (match) setSelectedCredential(match)
  }, [credentials])

  const handleSelectCredential = (id: string) => { const cred = credentials.find(c => c.id === id); if (cred) setSelectedCredential(cred) }
  const handleRemoveCredential = () => { setSelectedCredential(null); form.setValue('provider_credential_id', ''); form.setValue('provider', ''); form.setValue('model', '') }

  const onSubmit = async (data: CreateAgentFormData) => {
    if (!selectedCredential) { toast.error('Select a provider credential first'); return }
    try {
      const payloadSettings: Record<string, unknown> = {}
      if (isCustom) { const baseUrl = getCredentialBaseUrl(selectedCredential); if (baseUrl) payloadSettings.base_url = baseUrl }
      if (outputEnabled) {
        let parsedSchema: unknown = null
        try { parsedSchema = outputSchema ? JSON.parse(outputSchema) : null } catch { setOutputSchemaError('Invalid JSON schema'); return }
        payloadSettings.response_format = { enabled: true, type: 'json', schema: parsedSchema, strict: outputStrict }
      }
      const payload: Record<string, unknown> = {
        project_id: projectId!, name: data.name, provider: selectedCredential.provider,
        model: isCustom ? getCredentialModel(selectedCredential) : data.model,
        behavior_spec: behaviorToSpec({ ...behaviorFromSpec(), objective: data.objective || '' }),
        description: data.description || '', temperature: data.temperature, max_output_tokens: data.max_output_tokens,
        provider_credential_id: selectedCredential.id, session_mode: data.session_mode || 'stateful',
        settings: Object.keys(payloadSettings).length > 0 ? payloadSettings : undefined,
      }
      const agent = await createAgent.mutateAsync(payload as any)
      toast.success('Agent created')
      navigate(p(projectId!, 'agents', agent.id, 'playground'))
    } catch (err) { toast.error(err instanceof Error ? err.message : 'Failed to create agent') }
  }

  const nameValue = form.watch('name')
  const disabledReason = () => {
    if (!selectedCredential) return 'Add a provider credential to continue.'
    if (!nameValue) return 'Agent name is required.'
    if (!projectId) return 'Project ID is missing.'
    if (isCustom) {
      if (!getCredentialModel(selectedCredential)) return 'Custom credentials require a model in their metadata.'
      if (!getCredentialBaseUrl(selectedCredential)) return 'Custom credentials require a base URL.'
    }
    if (isStandard && !form.watch('model')) return 'Select a model to continue.'
    return null
  }
  const reason = disabledReason()
  const customMissingModel = Boolean(isCustom && selectedCredential && !getCredentialModel(selectedCredential))
  const customMissingBaseUrl = Boolean(isCustom && selectedCredential && !getCredentialBaseUrl(selectedCredential))

  return (
    <div className="max-w-4xl">
      <PageHeader title="Create Agent" description="Configure a new Agent without changing its runtime contract." eyebrow="Build / Agent" />
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3">
        <SectionBlock title="Agent details" density="compact">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field><FieldLabel>Name</FieldLabel><Input {...form.register('name')} error={form.formState.errors.name?.message} placeholder="My Agent" /></Field>
            <Field><FieldLabel>Description</FieldLabel><Input {...form.register('description')} placeholder="Optional description" /></Field>
          </div>
        </SectionBlock>

        <SectionBlock title="Model credential" density="compact">
          {selectedCredential ? (
            <TechnicalListItem
              label={selectedCredential.name}
              description={providerLabels[selectedCredential.provider] || selectedCredential.provider}
              meta={isCustom ? [getCredentialModel(selectedCredential) || 'model not configured', getCredentialBaseUrl(selectedCredential) || 'base URL not configured'].join(' · ') : undefined}
              leading={<Badge variant="secondary">{providerLabels[selectedCredential.provider] || selectedCredential.provider}</Badge>}
              trailing={<div className="flex items-center gap-1.5"><Badge variant={selectedCredential.status === 'active' ? 'success' : 'secondary'}>{selectedCredential.status || 'active'}</Badge><Button type="button" size="sm" variant="outline" onClick={() => setShowAddCredential(true)}>Change</Button><Button type="button" size="sm" variant="ghost" onClick={handleRemoveCredential}>Remove</Button></div>}
            />
          ) : credentials.length > 0 ? (
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center"><Select value="" onChange={(e) => handleSelectCredential(e.target.value)} options={[{ value: '', label: 'Select a credential' }, ...credentials.map(c => ({ value: c.id, label: `${c.name} (${providerLabels[c.provider] || c.provider})` }))]} className="sm:max-w-md" /><Button type="button" size="sm" variant="outline" onClick={() => setShowAddCredential(true)}>Add credential</Button></div>
          ) : (
            <EmptyStatePanel compact title="No provider credential" description="Add an API key to connect this Agent to a model provider." action={<Button type="button" size="sm" variant="outline" onClick={() => setShowAddCredential(true)}>Add credential</Button>} />
          )}
        </SectionBlock>

        {customMissingModel ? <Alert variant="destructive"><AlertDescription>This custom credential is missing a model. Recreate the credential with a model name.</AlertDescription></Alert> : null}
        {customMissingBaseUrl ? <Alert variant="destructive"><AlertDescription>This custom credential is missing a base URL. Recreate the credential with a base URL.</AlertDescription></Alert> : null}

        {isStandard ? <SectionBlock title="Model" density="compact"><Field><FieldLabel>Generation model</FieldLabel><Select {...form.register('model')} options={availableModels} /></Field></SectionBlock> : null}

        <SectionBlock title="Runtime" density="compact">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field><FieldLabel>Session mode</FieldLabel><Select {...form.register('session_mode')} options={[{ value: 'stateful', label: 'Stateful conversation' }, { value: 'stateless', label: 'Stateless request' }]} /></Field>
            <Field><FieldLabel>Temperature</FieldLabel><Input type="number" step="0.1" min="0" max="2" {...form.register('temperature')} /></Field>
            <Field><FieldLabel>Max output tokens</FieldLabel><Input type="number" step="1" min="1" {...form.register('max_output_tokens')} /></Field>
          </div>
        </SectionBlock>

        <SectionBlock title="Behavior" density="compact"><Field><FieldLabel htmlFor="agent-objective">Objective</FieldLabel><Textarea id="agent-objective" {...form.register('objective')} placeholder="What primary outcome should this Agent achieve?" className="min-h-24" /></Field></SectionBlock>

        <SectionBlock
          title="Advanced API output"
          density="compact"
          actions={<Button type="button" size="sm" variant="ghost" onClick={() => setShowAdvancedOutput(!showAdvancedOutput)}>{showAdvancedOutput ? <ChevronDown className="mr-1 h-3.5 w-3.5" /> : <ChevronRight className="mr-1 h-3.5 w-3.5" />}<FileJson className="mr-1 h-3.5 w-3.5" />{showAdvancedOutput ? 'Hide' : 'Configure'}</Button>}
        >
          {showAdvancedOutput ? <div className="space-y-3"><label className="flex items-center gap-2 font-mono text-[10px] text-slate-200"><Checkbox id="create-output-enabled" checked={outputEnabled} onChange={(e) => { setOutputEnabled(e.target.checked); if (!e.target.checked) setOutputSchemaError(null) }} />Enable JSON output</label><Field><FieldLabel>JSON schema</FieldLabel><JsonEditor value={outputSchema} onChange={(val) => { setOutputSchema(val); if (outputSchemaError) { try { JSON.parse(val); setOutputSchemaError(null) } catch { /* keep invalid state */ } } }} editable disabled={!outputEnabled} actions={['format', 'validate', 'clear']} minHeight={150} placeholder='{ "type": "object", ... }' error={outputSchemaError} /></Field><label className="flex items-center gap-2 font-mono text-[10px] text-slate-200"><Checkbox id="create-output-strict" checked={outputStrict} onChange={(e) => setOutputStrict(e.target.checked)} disabled={!outputEnabled} />Strict mode</label></div> : <p className="font-sans text-xs text-muted">Optional structured JSON response contract for API consumers.</p>}
        </SectionBlock>

        <div className="flex flex-col items-end gap-1 border-t border-border pt-3">
          {reason ? <p className="font-sans text-[11px] text-muted">{reason}</p> : null}
          <div className="flex gap-2"><Button type="button" variant="outline" onClick={() => navigate(-1)}>Cancel</Button><Button type="submit" loading={createAgent.isPending} disabled={Boolean(reason)}>Create Agent</Button></div>
        </div>
      </form>

      <AddProviderCredentialModal open={showAddCredential} onClose={() => setShowAddCredential(false)} projectId={projectId!} onCredentialCreated={handleCredentialCreated} />
    </div>
  )
}
