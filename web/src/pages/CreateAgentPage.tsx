import { useNavigate, useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useCreateAgent } from '@/features/agents/hooks'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { createAgentSchema, type CreateAgentFormData } from '@/features/agents/schemas'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Select } from '@/components/ui/Select'
import { orgProjectPath } from '@/lib/constants/routes'
import { toast } from 'sonner'

const providers = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google' },
  { value: 'custom', label: 'Custom' },
]

const models: Record<string, { value: string; label: string }[]> = {
  openai: [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
  ],
  anthropic: [
    { value: 'claude-3-5-sonnet', label: 'Claude 3.5 Sonnet' },
    { value: 'claude-3-haiku', label: 'Claude 3 Haiku' },
  ],
  google: [
    { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
    { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
  ],
  custom: [
    { value: 'custom-model', label: 'Custom Model' },
  ],
}

export default function CreateAgentPage() {
  const { organizationId, projectId } = useParams<{ organizationId?: string; projectId: string }>()
  const navigate = useNavigate()
  const createAgent = useCreateAgent(projectId)
  const { data: credentials } = useCredentials(projectId)

  const p = (projId: string, ...segments: string[]) => orgProjectPath(organizationId, projId, ...segments)

  const form = useForm<CreateAgentFormData>({
    resolver: zodResolver(createAgentSchema),
    defaultValues: {
      provider: 'openai',
      model: 'gpt-4o',
      temperature: 0.7,
      max_output_tokens: 2048,
    },
  })

  const selectedProvider = form.watch('provider')
  const availableModels = models[selectedProvider] || models.openai

  const onSubmit = async (data: CreateAgentFormData) => {
    try {
      const agent = await createAgent.mutateAsync({
        project_id: projectId!,
        name: data.name,
        provider: data.provider,
        model: data.model,
        system_prompt: data.system_prompt || '',
        description: data.description || '',
        temperature: data.temperature,
        max_output_tokens: data.max_output_tokens,
        provider_credential_id: data.provider_credential_id || undefined,
      })
      toast.success('Agent created')
      navigate(p(projectId!, 'agents', agent.id))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create agent')
    }
  }

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
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-muted mb-1">Provider</label>
                <Select {...form.register('provider')} options={providers} />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted mb-1">Model</label>
                <Select {...form.register('model')} options={availableModels} />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted mb-1">Credential (optional)</label>
              <select
                {...form.register('provider_credential_id')}
                className="flex h-9 w-full rounded-lg border border-border bg-transparent px-3 py-1 text-sm"
              >
                <option value="">No credential</option>
                {(credentials || []).map((c) => (
                  <option key={c.id} value={c.id}>{c.name} ({c.provider})</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-muted mb-1">Temperature</label>
                <Input type="number" step="0.1" min="0" max="2" {...form.register('temperature')} />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted mb-1">Max Output Tokens</label>
                <Input type="number" step="1" min="1" {...form.register('max_output_tokens')} />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted mb-1">System Prompt</label>
              <Textarea
                {...form.register('system_prompt')}
                placeholder="You are a helpful AI assistant..."
                className="min-h-[120px]"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => navigate(-1)}>Cancel</Button>
              <Button type="submit" loading={createAgent.isPending}>Create Agent</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
