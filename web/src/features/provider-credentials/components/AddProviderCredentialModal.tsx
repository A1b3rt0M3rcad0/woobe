import { useState, useEffect } from 'react'
import { useCreateCredential, useUpdateCredential } from '@/features/provider-credentials/hooks'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { toast } from 'sonner'
import type { ProviderCredential } from '@/features/provider-credentials/types'

const OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'

const providers = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'custom', label: 'OpenAI Compatible' },
  { value: 'openrouter', label: 'OpenRouter' },
]

const defaultNames: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible Provider',
  openrouter: 'OpenRouter',
}

function buildCredentialMetadata(provider: string, baseUrl: string): Record<string, string> {
  if (provider === 'custom') {
    return {
      provider_family: 'openai',
      compatibility: 'compatible',
      base_url: baseUrl.trim(),
      model_discovery_strategy: 'openai_compatible_models',
    }
  }
  if (provider === 'openrouter') {
    return {
      provider_family: 'openrouter',
      compatibility: 'native',
      base_url: OPENROUTER_BASE_URL,
      model_discovery_strategy: 'openrouter_models',
    }
  }
  return {
    provider_family: 'openai',
    compatibility: 'native',
    model_discovery_strategy: 'openai_models',
  }
}

interface AddProviderCredentialModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  onCredentialCreated: (credentialId: string) => void
  credential?: ProviderCredential | null
}

export function AddProviderCredentialModal({ open, onClose, projectId, onCredentialCreated, credential }: AddProviderCredentialModalProps) {
  const createCredential = useCreateCredential()
  const updateCredential = useUpdateCredential()
  const isEditing = Boolean(credential)

  const [provider, setProvider] = useState('openai')
  const [name, setName] = useState(defaultNames.openai)
  const [secret, setSecret] = useState('')
  const [baseUrl, setBaseUrl] = useState('')

  useEffect(() => {
    if (credential) {
      setProvider(credential.provider)
      setName(credential.name)
      setSecret('')
      const meta = credential.metadata || {}
      setBaseUrl(meta.base_url || '')
    } else {
      setProvider('openai')
      setName(defaultNames.openai)
      setSecret('')
      setBaseUrl('')
    }
  }, [credential, open])

  useEffect(() => {
    if (isEditing) return
    setName(defaultNames[provider] || '')
    if (provider !== 'custom') {
      setBaseUrl('')
    }
  }, [provider, isEditing])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      toast.error('Name is required')
      return
    }
    if (!isEditing && !secret.trim()) {
      toast.error('API key is required')
      return
    }
    if (!providers.some((item) => item.value === provider)) {
      toast.error('Provider is not supported')
      return
    }
    if (provider === 'custom' && !baseUrl.trim()) {
      toast.error('Base URL is required for OpenAI Compatible providers')
      return
    }

    try {
      const metadata = buildCredentialMetadata(provider, baseUrl)
      if (isEditing && credential) {
        const payload: Record<string, unknown> = {}
        if (name.trim() !== credential.name) payload.name = name.trim()
        if (provider !== credential.provider) payload.provider = provider
        if (secret.trim()) payload.secret = secret.trim()
        payload.metadata = metadata
        await updateCredential.mutateAsync({ id: credential.id, data: payload as any })
        toast.success('Credential updated')
        onCredentialCreated(credential.id)
      } else {
        const payload: Record<string, unknown> = {
          project_id: projectId,
          provider,
          name: name.trim(),
          secret: secret.trim(),
          metadata,
        }
        const result = await createCredential.mutateAsync(payload as any)
        toast.success('Credential added')
        onCredentialCreated(result.id)
      }
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save credential')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title={isEditing ? 'Edit Provider Credential' : 'Add Provider Credential'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-muted">Provider</label>
          <Select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            options={providers}
          />
          <p className="mt-1 text-xs text-muted">Credentials only store access. Models are selected separately from the provider catalog when possible.</p>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-muted">Name</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My provider key"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-muted">API Key</label>
          <Input
            type="password"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            placeholder={isEditing ? 'Leave blank to keep current' : 'Paste your API key'}
          />
        </div>
        {provider === 'custom' && (
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Base URL</label>
            <Input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.example.com/v1"
            />
            <p className="mt-1 text-xs text-muted">Use this for OpenAI-compatible gateways. Model discovery will try GET /models and fall back to manual model entry if unavailable.</p>
          </div>
        )}
        {provider === 'openrouter' && (
          <p className="rounded-lg border border-border bg-background p-3 text-xs text-muted">OpenRouter uses <code>{OPENROUTER_BASE_URL}</code> automatically. Models are loaded from the OpenRouter catalog.</p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={createCredential.isPending || updateCredential.isPending}>
            {isEditing ? 'Save Changes' : 'Save'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
