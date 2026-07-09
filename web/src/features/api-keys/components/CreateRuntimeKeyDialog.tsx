import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { KeyRound } from 'lucide-react'
import { toast } from 'sonner'
import { CopyButton } from '@/components/common/CopyButton'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { useCreateRuntimeApiKey } from '@/features/api-keys/hooks'
import {
  createRuntimeApiKeySchema,
  type CreateRuntimeApiKeyFormData,
} from '@/features/api-keys/schemas'
import type {
  CreateApiKeyResponse,
  RuntimeEnvironment,
  RuntimeInterface,
} from '@/features/api-keys/types'

interface CreateRuntimeKeyDialogProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  agentName: string
  environment: RuntimeEnvironment
  onCreated: (apiKey: CreateApiKeyResponse) => void
}

type ExpirationPreset = '7d' | '30d' | '90d' | '365d' | 'custom' | 'never'

const INTERFACES: Array<{ value: RuntimeInterface; label: string; description: string }> = [
  { value: 'http', label: 'HTTP', description: 'Synchronous requests through POST /v1/run' },
  { value: 'stream', label: 'Streaming', description: 'SSE streaming through POST /v1/run/stream' },
  { value: 'jobs', label: 'Jobs', description: 'Asynchronous execution and job polling' },
]

const EXPIRATIONS: Array<{ value: ExpirationPreset; label: string }> = [
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: '90d', label: '90 days' },
  { value: '365d', label: '1 year' },
  { value: 'custom', label: 'Custom' },
  { value: 'never', label: 'No expiration' },
]

function expirationValue(preset: ExpirationPreset, customValue?: string): string | null {
  if (preset === 'never') return null
  if (preset === 'custom') return customValue ? new Date(customValue).toISOString() : null
  const days = preset === '7d' ? 7 : preset === '30d' ? 30 : preset === '90d' ? 90 : 365
  const value = new Date()
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString()
}

export function CreateRuntimeKeyDialog({
  open,
  onClose,
  projectId,
  agentId,
  agentName,
  environment,
  onCreated,
}: CreateRuntimeKeyDialogProps) {
  const createRuntimeKey = useCreateRuntimeApiKey(projectId)
  const [expiration, setExpiration] = useState<ExpirationPreset>('90d')
  const [createdKey, setCreatedKey] = useState<CreateApiKeyResponse | null>(null)
  const form = useForm<CreateRuntimeApiKeyFormData>({
    resolver: zodResolver(createRuntimeApiKeySchema),
    defaultValues: {
      name: '',
      interfaces: ['http', 'stream', 'jobs'],
      expires_at: '',
    },
  })

  useEffect(() => {
    if (!open) return
    setCreatedKey(null)
    setExpiration('90d')
    form.reset({
      name: `${agentName} · ${environment === 'production' ? 'Production' : 'Staging'}`,
      interfaces: ['http', 'stream', 'jobs'],
      expires_at: '',
    })
  }, [open, agentName, environment, form])

  const close = () => {
    setCreatedKey(null)
    form.reset()
    onClose()
  }

  const submit = form.handleSubmit(async (data) => {
    if (expiration === 'custom' && !data.expires_at) {
      form.setError('expires_at', { message: 'Select an expiration date' })
      return
    }
    try {
      const result = await createRuntimeKey.mutateAsync({
        name: data.name,
        agent_id: agentId,
        environment,
        interfaces: data.interfaces,
        expires_at: expirationValue(expiration, data.expires_at),
      })
      setCreatedKey(result)
      onCreated(result)
      toast.success('Runtime Key created')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create Runtime Key')
    }
  })

  return (
    <Dialog open={open} onClose={close} title={createdKey ? 'Runtime Key created' : 'Create Runtime Key'} className="max-w-2xl">
      {createdKey ? (
        <div className="space-y-5">
          <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <KeyRound className="h-4 w-4 text-primary-light" />
              This secret will only be shown once
            </div>
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-border/80 bg-background/80 p-3">
              <code className="min-w-0 flex-1 break-all text-xs text-white">{createdKey.key}</code>
              <CopyButton text={createdKey.key} />
            </div>
          </div>
          <div>
            <p className="text-xs font-medium text-muted">Environment setup</p>
            <div className="mt-2 flex items-center gap-2 rounded-lg border border-border/80 bg-background/60 p-3">
              <code className="min-w-0 flex-1 break-all text-xs text-muted">export WOOBE_API_KEY=&quot;{createdKey.key}&quot;</code>
              <CopyButton text={`export WOOBE_API_KEY="${createdKey.key}"`} />
            </div>
          </div>
          <div className="flex justify-end">
            <Button onClick={close}>Done</Button>
          </div>
        </div>
      ) : (
        <form className="space-y-5" onSubmit={submit}>
          <div>
            <label className="text-xs font-medium text-muted">Name</label>
            <Input className="mt-2" {...form.register('name')} />
            {form.formState.errors.name && <p className="mt-1 text-xs text-red-300">{form.formState.errors.name.message}</p>}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-border/80 bg-background/45 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Agent</p>
              <p className="mt-1 truncate text-sm font-medium text-white">{agentName}</p>
            </div>
            <div className="rounded-xl border border-border/80 bg-background/45 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Environment</p>
              <p className="mt-1 text-sm font-medium capitalize text-white">{environment}</p>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-muted">Allowed interfaces</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              {INTERFACES.map((item) => {
                const selected = form.watch('interfaces').includes(item.value)
                return (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => {
                      const current = form.getValues('interfaces')
                      form.setValue(
                        'interfaces',
                        selected ? current.filter((value) => value !== item.value) : [...current, item.value],
                        { shouldValidate: true },
                      )
                    }}
                    className={`rounded-xl border p-3 text-left transition-colors ${selected ? 'border-primary/35 bg-primary/10' : 'border-border/80 bg-background/45 hover:border-primary/25'}`}
                  >
                    <p className="text-sm font-medium text-white">{item.label}</p>
                    <p className="mt-1 text-[11px] leading-4 text-muted">{item.description}</p>
                  </button>
                )
              })}
            </div>
            {form.formState.errors.interfaces && <p className="mt-1 text-xs text-red-300">{form.formState.errors.interfaces.message}</p>}
          </div>

          <div>
            <p className="text-xs font-medium text-muted">Expiration</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {EXPIRATIONS.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setExpiration(item.value)}
                  className={`rounded-lg border px-3 py-2 text-xs transition-colors ${expiration === item.value ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-border/80 bg-background/45 text-muted hover:text-white'}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
            {expiration === 'custom' && (
              <div className="mt-3">
                <Input type="datetime-local" {...form.register('expires_at')} />
                {form.formState.errors.expires_at && <p className="mt-1 text-xs text-red-300">{form.formState.errors.expires_at.message}</p>}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 border-t border-border/80 pt-4">
            <Button type="button" variant="secondary" onClick={close}>Cancel</Button>
            <Button type="submit" loading={createRuntimeKey.isPending}>Create Runtime Key</Button>
          </div>
        </form>
      )}
    </Dialog>
  )
}
