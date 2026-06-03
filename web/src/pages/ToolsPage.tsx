import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useTools, useCreateTool, useSecrets, useCreateSecret } from '@/features/tools/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Select } from '@/components/ui/Select'
import { Tabs } from '@/components/ui/Tabs'
import { StatusBadge } from '@/components/common/StatusBadge'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { createToolSchema, createSecretSchema, type CreateToolFormData, type CreateSecretFormData } from '@/features/tools/schemas'
import { Wrench, Key, Plus } from 'lucide-react'
import { toast } from 'sonner'
import type { Tool, Secret } from '@/features/tools/types'

const riskOptions = [
  { value: 'read_only', label: 'Read Only' },
  { value: 'write', label: 'Write' },
  { value: 'destructive', label: 'Destructive' },
  { value: 'restricted', label: 'Restricted' },
]

export default function ToolsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: tools, isLoading: toolsLoading, isError: toolsError, refetch: refetchTools } = useTools(projectId)
  const createTool = useCreateTool()
  const { data: secrets, isLoading: secLoading } = useSecrets(projectId)
  const createSecret = useCreateSecret()
  const [showTool, setShowTool] = useState(false)
  const [showSecret, setShowSecret] = useState(false)

  const toolForm = useForm<CreateToolFormData>({
    resolver: zodResolver(createToolSchema),
    defaultValues: { type: 'http_mcp', risk_level: 'read_only' },
  })

  const secretForm = useForm<CreateSecretFormData>({
    resolver: zodResolver(createSecretSchema),
  })

  const handleCreateTool = async (data: CreateToolFormData) => {
    try {
      await createTool.mutateAsync({
        project_id: projectId!,
        agent_id: projectId!,
        name: data.name,
        description: data.description,
        type: data.type,
        risk_level: data.risk_level || 'read_only',
        config: data.config ? JSON.parse(data.config) : undefined,
        input_schema: data.input_schema ? JSON.parse(data.input_schema) : undefined,
        output_schema: data.output_schema ? JSON.parse(data.output_schema) : undefined,
        timeout_ms: data.timeout_ms,
      })
      toast.success('Tool created')
      setShowTool(false)
      toolForm.reset()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed')
    }
  }

  const handleCreateSecret = async (data: CreateSecretFormData) => {
    try {
      await createSecret.mutateAsync({
        project_id: projectId!,
        name: data.name,
        type: data.type || 'custom',
        value: data.value,
      })
      toast.success('Secret created')
      setShowSecret(false)
      secretForm.reset()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed')
    }
  }

  if (toolsLoading || secLoading) return <LoadingState />
  if (toolsError) return <ErrorState onRetry={refetchTools} />

  const tabs = [
    {
      id: 'tools',
      label: 'Tools',
      content: (
        <div>
          <div className="flex justify-end mb-4">
            <Button size="sm" onClick={() => setShowTool(true)}>
              <Plus className="mr-1 h-4 w-4" />
              New Tool
            </Button>
          </div>
          {tools && tools.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {tools.map((t: Tool) => (
                <Card key={t.id}>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between text-sm">
                      <span>{t.name}</span>
                      <StatusBadge status={t.status} />
                    </CardTitle>
                    <CardDescription>{t.description || t.type}</CardDescription>
                  </CardHeader>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState icon={<Wrench className="h-12 w-12" />} title="No tools" description="Create tools to give your agents external capabilities." />
          )}
        </div>
      ),
    },
    {
      id: 'secrets',
      label: 'Secrets',
      content: (
        <div>
          <div className="flex justify-end mb-4">
            <Button size="sm" onClick={() => setShowSecret(true)}>
              <Plus className="mr-1 h-4 w-4" />
              New Secret
            </Button>
          </div>
          {secrets && secrets.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {secrets.map((s: Secret) => (
                <Card key={s.id}>
                  <CardHeader>
                    <CardTitle className="text-sm">{s.name}</CardTitle>
                    <CardDescription>{s.type}</CardDescription>
                  </CardHeader>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState icon={<Key className="h-12 w-12" />} title="No secrets" description="Store API keys and credentials securely." />
          )}
        </div>
      ),
    },
  ]

  return (
    <div>
      <PageHeader title="Tools" description="External tools and secrets for your agents" />
      <Tabs tabs={tabs} />

      <Dialog open={showTool} onClose={() => setShowTool(false)} title="Create Tool">
        <form onSubmit={toolForm.handleSubmit(handleCreateTool)} className="space-y-4">
          <Input {...toolForm.register('name')} error={toolForm.formState.errors.name?.message} placeholder="Tool name" />
          <Textarea {...toolForm.register('description')} placeholder="Description" />
          <Select {...toolForm.register('type')} options={[{ value: 'http_mcp', label: 'HTTP MCP' }, { value: 'function', label: 'Function' }]} placeholder="Type" />
          <Select {...toolForm.register('risk_level')} options={riskOptions} placeholder="Risk level" />
          <Textarea {...toolForm.register('config')} placeholder='Config JSON (optional)' className="font-mono text-xs min-h-[80px]" />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setShowTool(false)}>Cancel</Button>
            <Button type="submit" loading={createTool.isPending}>Create</Button>
          </div>
        </form>
      </Dialog>

      <Dialog open={showSecret} onClose={() => setShowSecret(false)} title="Create Secret">
        <form onSubmit={secretForm.handleSubmit(handleCreateSecret)} className="space-y-4">
          <Input {...secretForm.register('name')} error={secretForm.formState.errors.name?.message} placeholder="Secret name" />
          <Select {...secretForm.register('type')} options={[{ value: 'custom', label: 'Custom' }, { value: 'api_key', label: 'API Key' }, { value: 'bearer', label: 'Bearer Token' }]} placeholder="Type" />
          <Input type="password" {...secretForm.register('value')} error={secretForm.formState.errors.value?.message} placeholder="Secret value" />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setShowSecret(false)}>Cancel</Button>
            <Button type="submit" loading={createSecret.isPending}>Create</Button>
          </div>
        </form>
      </Dialog>
    </div>
  )
}
