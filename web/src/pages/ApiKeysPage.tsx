import { useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  useApiKeys,
  useCreateApiKey,
  useRevokeApiKey,
  useRotateApiKey,
} from '@/features/api-keys/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Table } from '@/components/ui/Table'
import { StatusBadge } from '@/components/common/StatusBadge'
import { CopyButton } from '@/components/common/CopyButton'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  createApiKeySchema,
  type CreateApiKeyFormData,
} from '@/features/api-keys/schemas'
import { AlertTriangle, Ban, Key, Plus, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'
import type { ApiKey, ApiKeyScope } from '@/features/api-keys/types'

const SCOPE_OPTIONS: Array<{ value: ApiKeyScope; label: string }> = [
  { value: 'runtime:execute', label: 'Execute runtime requests' },
  { value: 'traces:read', label: 'Read traces' },
  { value: 'usage:read', label: 'Read usage' },
]

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Never'
}

export default function ApiKeysPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: keys, isLoading, isError, error, refetch } = useApiKeys(projectId)
  const createKey = useCreateApiKey(projectId)
  const revokeKey = useRevokeApiKey(projectId)
  const rotateKey = useRotateApiKey(projectId)
  const [showCreate, setShowCreate] = useState(false)
  const [newKey, setNewKey] = useState<string | null>(null)

  const form = useForm<CreateApiKeyFormData>({
    resolver: zodResolver(createApiKeySchema),
    defaultValues: {
      name: '',
      scopes: ['runtime:execute'],
      expires_at: '',
    },
  })

  const handleCreate = async (data: CreateApiKeyFormData) => {
    try {
      const result = await createKey.mutateAsync({
        name: data.name,
        scopes: data.scopes,
        expires_at: data.expires_at ? new Date(data.expires_at).toISOString() : null,
      })
      setNewKey(result.key)
      toast.success('API key created')
      form.reset({ name: '', scopes: ['runtime:execute'], expires_at: '' })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create key')
    }
  }

  const handleRevoke = async (apiKey: ApiKey) => {
    if (!window.confirm(`Revoke API key “${apiKey.name}”?`)) return
    try {
      await revokeKey.mutateAsync(apiKey.id)
      toast.success('API key revoked')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to revoke key')
    }
  }

  const handleRotate = async (apiKey: ApiKey) => {
    if (!window.confirm(`Rotate API key “${apiKey.name}”? The current key will stop working immediately.`)) return
    try {
      const result = await rotateKey.mutateAsync({ apiKeyId: apiKey.id })
      setNewKey(result.key)
      setShowCreate(true)
      toast.success('API key rotated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to rotate key')
    }
  }

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const columns = [
    { key: 'name', header: 'Name' },
    {
      key: 'key_prefix',
      header: 'Prefix',
      render: (key: ApiKey) => <code className="text-xs text-muted">{key.key_prefix}...</code>,
    },
    {
      key: 'scopes',
      header: 'Scopes',
      render: (key: ApiKey) => <span className="text-xs text-muted">{key.scopes.join(', ')}</span>,
    },
    {
      key: 'last_used_at',
      header: 'Last used',
      render: (key: ApiKey) => <span className="text-xs text-muted">{formatDate(key.last_used_at)}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (key: ApiKey) => <StatusBadge status={key.status} />,
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (key: ApiKey) => key.status === 'active' ? (
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void handleRotate(key)}
            disabled={rotateKey.isPending}
          >
            <RotateCcw className="mr-1 h-3.5 w-3.5" />
            Rotate
          </Button>
          <Button
            type="button"
            size="sm"
            variant="destructive"
            onClick={() => void handleRevoke(key)}
            disabled={revokeKey.isPending}
          >
            <Ban className="mr-1 h-3.5 w-3.5" />
            Revoke
          </Button>
        </div>
      ) : null,
    },
  ]

  return (
    <div>
      <PageHeader
        title="API Keys"
        description="Project-scoped credentials for runtime, traces, and usage APIs"
        actions={
          <Button onClick={() => { setNewKey(null); setShowCreate(true) }}>
            <Plus className="mr-2 h-4 w-4" />
            Create Key
          </Button>
        }
      />

      {keys && keys.length > 0 ? (
        <Card>
          <CardContent className="p-0">
            <Table columns={columns} data={keys} keyExtractor={(key) => key.id} />
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          icon={<Key className="h-12 w-12" />}
          title="No API keys"
          description="Create a project-scoped key to connect to the runtime."
          action={
            <Button onClick={() => { setNewKey(null); setShowCreate(true) }}>
              <Plus className="mr-2 h-4 w-4" />
              Create Key
            </Button>
          }
        />
      )}

      <Dialog
        open={showCreate}
        onClose={() => { setShowCreate(false); setNewKey(null) }}
        title={newKey ? 'API Key Ready' : 'Create API Key'}
      >
        {newKey ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-yellow-500/50 bg-yellow-500/10 p-4">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-yellow-400" />
                <div>
                  <p className="text-sm font-medium text-yellow-400">Copy this key now</p>
                  <p className="text-xs text-yellow-400/70">It is shown once and cannot be recovered later.</p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-3">
              <code className="flex-1 break-all text-sm">{newKey}</code>
              <CopyButton text={newKey} />
            </div>
            <Button className="w-full" onClick={() => { setShowCreate(false); setNewKey(null) }}>
              Done
            </Button>
          </div>
        ) : (
          <form onSubmit={form.handleSubmit(handleCreate)} className="space-y-4">
            <Input
              {...form.register('name')}
              error={form.formState.errors.name?.message}
              placeholder="Key name"
            />
            <div className="space-y-2">
              <p className="text-sm font-medium">Scopes</p>
              {SCOPE_OPTIONS.map((scope) => (
                <label key={scope.value} className="flex items-center gap-2 text-sm text-muted">
                  <input type="checkbox" value={scope.value} {...form.register('scopes')} />
                  {scope.label}
                </label>
              ))}
              {form.formState.errors.scopes?.message && (
                <p className="text-xs text-red-400">{form.formState.errors.scopes.message}</p>
              )}
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium" htmlFor="api-key-expires-at">Expiration (optional)</label>
              <Input id="api-key-expires-at" type="datetime-local" {...form.register('expires_at')} />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button type="submit" loading={createKey.isPending}>Create</Button>
            </div>
          </form>
        )}
      </Dialog>
    </div>
  )
}
