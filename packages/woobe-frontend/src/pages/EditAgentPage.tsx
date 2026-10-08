import { AgentBehaviorFields } from '@/features/agents/components/AgentBehaviorSettings'
import { behaviorFromSpec, behaviorToSpec } from '@/features/agents/behavior'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import { Alert, AlertDescription, EmptyStatePanel, Field, FieldLabel, SectionBlock, TechnicalListItem } from '@woobe/ui'
import { useAgent, useUpdateAgent } from '@/features/agents/hooks'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { createAgentSchema, type CreateAgentFormData } from '@/features/agents/schemas'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { workspaceProjectPath } from '@/lib/constants/routes'
import type { ProviderCredential } from '@/features/provider-credentials/types'

const modelOptions: Record<string, { value: string; label: string }[]> = {
  openai: [{ value: 'gpt-4o-mini', label: 'GPT-4o Mini' }, { value: 'gpt-4o', label: 'GPT-4o' }, { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' }, { value: 'gpt-4.1', label: 'GPT-4.1' }],
  anthropic: [{ value: 'claude-3-5-sonnet-latest', label: 'Claude 3.5 Sonnet' }, { value: 'claude-3-5-haiku-latest', label: 'Claude 3.5 Haiku' }, { value: 'claude-3-opus-latest', label: 'Claude 3 Opus' }],
  google: [{ value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' }, { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' }, { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' }],
}
const defaultModels: Record<string, string> = { openai: 'gpt-4o-mini', anthropic: 'claude-3-5-haiku-latest', google: 'gemini-1.5-flash' }
const providerLabels: Record<string, string> = { openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google', custom: 'Custom' }
const statusOptions = [{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }]
function getCredentialModel(credential: ProviderCredential): string { return credential.metadata?.model || credential.metadata?.model_name || '' }
function getCredentialBaseUrl(credential: ProviderCredential): string { return credential.metadata?.base_url || '' }

export default function EditAgentPage() {
  const { workspaceId, projectId, agentId } = useParams<{ workspaceId?: string; projectId: string; agentId: string }>()
  const navigate = useNavigate()
  const { data: agent, isLoading, isError, error } = useAgent(agentId)
  const [baseRevision, setBaseRevision] = useState<number | undefined>()
  const updateAgent = useUpdateAgent(agentId, baseRevision)
  const { data: credentials = [], refetch: refetchCredentials } = useCredentials(projectId)
  const [showAddCredential, setShowAddCredential] = useState(false)
  const [selectedCredential, setSelectedCredential] = useState<ProviderCredential | null>(null)
  const [behavior, setBehavior] = useState(() => behaviorFromSpec())
  const [formReady, setFormReady] = useState(false)
  const pendingCredentialId = useRef<string | null>(null)
  const p = (projId: string, ...segments: string[]) => workspaceProjectPath(workspaceId, projId, ...segments)
  const form = useForm<CreateAgentFormData>({ resolver: zodResolver(createAgentSchema) })

  useEffect(() => { setFormReady(false); setBaseRevision(undefined) }, [agentId])

  useEffect(() => {
    if (!agent || !credentials.length || formReady) return
    const cred = credentials.find(c => c.id === agent.provider_credential_id) || null
    setSelectedCredential(cred)
    form.reset({ name: agent.name, description: agent.description || '', provider: agent.provider, model: agent.model, temperature: agent.temperature ?? 0.7, max_output_tokens: agent.max_output_tokens ?? 2048, provider_credential_id: agent.provider_credential_id || '', session_mode: (agent.session_mode === 'stateless' ? 'stateless' : 'stateful') as 'stateful' | 'stateless', status: agent.status === 'active' ? 'active' : 'inactive' })
    setBehavior(behaviorFromSpec(agent.behavior_spec, agent.system_prompt))
    setBaseRevision(agent.revision)
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
      const payload: Record<string, unknown> = { name: data.name, provider: selectedCredential.provider, model: isCustom ? getCredentialModel(selectedCredential) : data.model, behavior_spec: behaviorToSpec(behavior), description: data.description || '', temperature: data.temperature, max_output_tokens: data.max_output_tokens, provider_credential_id: selectedCredential.id, session_mode: data.session_mode || 'stateful', status: data.status }
      if (isCustom) { const baseUrl = getCredentialBaseUrl(selectedCredential); if (baseUrl) payload.settings = { base_url: baseUrl } }
      const saved = await updateAgent.mutateAsync(payload as any)
      setBaseRevision(saved.revision)
      toast.success('Agent updated')
    } catch (err) { toast.error(err instanceof Error ? err.message : 'Failed to update agent') }
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
  const customMissingModel = Boolean(isCustom && selectedCredential && !getCredentialModel(selectedCredential))
  const customMissingBaseUrl = Boolean(isCustom && selectedCredential && !getCredentialBaseUrl(selectedCredential))

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={() => navigate(p(projectId!, 'agents'))} />
  if (!agent) return <ErrorState message="Agent not found" />

  return (
    <div className="max-w-4xl">
      <PageHeader title="Edit Agent" description={`Update configuration for ${agent.name}`} eyebrow="Build / Agent" actions={<Button variant="ghost" size="sm" onClick={() => navigate(p(projectId!, 'agents', agentId!, 'playground'))}><ArrowLeft className="mr-1 h-3.5 w-3.5" />Back to Playground</Button>} />
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3">
        <SectionBlock title="Agent details" density="compact"><div className="grid gap-3 sm:grid-cols-2"><Field><FieldLabel>Name</FieldLabel><Input {...form.register('name')} error={form.formState.errors.name?.message} placeholder="My Agent" /></Field><Field><FieldLabel>Status</FieldLabel><Select {...form.register('status')} options={statusOptions} /></Field></div><Field className="mt-3"><FieldLabel>Description</FieldLabel><Input {...form.register('description')} placeholder="Optional description" /></Field></SectionBlock>

        <SectionBlock title="Model credential" density="compact">
          {selectedCredential ? <TechnicalListItem label={selectedCredential.name} description={providerLabels[selectedCredential.provider] || selectedCredential.provider} meta={isCustom ? [getCredentialModel(selectedCredential) || 'model not configured', getCredentialBaseUrl(selectedCredential) || 'base URL not configured'].join(' · ') : undefined} leading={<Badge variant="secondary">{providerLabels[selectedCredential.provider] || selectedCredential.provider}</Badge>} trailing={<div className="flex items-center gap-1.5"><Badge variant={selectedCredential.status === 'active' ? 'success' : 'secondary'}>{selectedCredential.status || 'active'}</Badge><Button type="button" size="sm" variant="outline" onClick={() => setShowAddCredential(true)}>Change</Button><Button type="button" size="sm" variant="ghost" onClick={handleRemoveCredential}>Remove</Button></div>} /> : credentials.length > 0 ? <div className="flex flex-col gap-2 sm:flex-row sm:items-center"><Select value="" onChange={(e) => handleSelectCredential(e.target.value)} options={[{ value: '', label: 'Select a credential' }, ...credentials.map(c => ({ value: c.id, label: `${c.name} (${providerLabels[c.provider] || c.provider})` }))]} className="sm:max-w-md" /><Button type="button" size="sm" variant="outline" onClick={() => setShowAddCredential(true)}>Add credential</Button></div> : <EmptyStatePanel compact title="No provider credential" description="Add an API key to connect this Agent to a model provider." action={<Button type="button" size="sm" variant="outline" onClick={() => setShowAddCredential(true)}>Add credential</Button>} />}
        </SectionBlock>

        {customMissingModel ? <Alert variant="destructive"><AlertDescription>This custom credential is missing a model. Recreate the credential with a model name.</AlertDescription></Alert> : null}
        {customMissingBaseUrl ? <Alert variant="destructive"><AlertDescription>This custom credential is missing a base URL. Recreate the credential with a base URL.</AlertDescription></Alert> : null}
        {isStandard ? <SectionBlock title="Model" density="compact"><Field><FieldLabel>Generation model</FieldLabel><Select value={form.watch('model')} onChange={(e) => form.setValue('model', e.target.value)} options={availableModels} /></Field></SectionBlock> : null}

        <SectionBlock title="Generation settings" density="compact"><div className="grid gap-3 sm:grid-cols-3"><Field><FieldLabel>Session mode</FieldLabel><Select {...form.register('session_mode')} options={[{ value: 'stateful', label: 'Stateful' }, { value: 'stateless', label: 'Stateless' }]} /></Field><Field><FieldLabel>Temperature</FieldLabel><Input type="number" step="0.1" min="0" max="2" {...form.register('temperature')} /></Field><Field><FieldLabel>Max output tokens</FieldLabel><Input type="number" step="1" min="1" {...form.register('max_output_tokens')} /></Field></div></SectionBlock>

        <AgentBehaviorFields behavior={behavior} onChange={setBehavior} agentName={nameValue} />
        <div className="flex flex-col items-end gap-1 border-t border-border pt-3">{reason ? <p className="font-sans text-[11px] text-muted">{reason}</p> : null}<div className="flex gap-2"><Button type="button" variant="outline" onClick={() => navigate(p(projectId!, 'agents', agentId!, 'playground'))}>Back</Button><Button type="submit" loading={updateAgent.isPending} disabled={Boolean(reason)}>Save Changes</Button></div></div>
      </form>

      <AddProviderCredentialModal open={showAddCredential} onClose={() => setShowAddCredential(false)} projectId={projectId!} credential={selectedCredential} onCredentialCreated={handleCredentialCreated} />
    </div>
  )
}
