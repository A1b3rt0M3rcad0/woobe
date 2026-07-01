import { useState, useEffect } from 'react'
import { useCreateCredential, useUpdateCredential } from '@/features/provider-credentials/hooks'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { toast } from 'sonner'
import type { ProviderCredential } from '@/features/provider-credentials/types'

const providers = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google' },
  { value: 'custom', label: 'Custom (OpenAI-compatible)' },
]

const defaultNames: Record<string, string> = {
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
  anthropic: 'Anthropic',
  google: 'Google',
  custom: 'Custom Provider',
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
      toast.error('Base URL is required for custom providers')
      return
    }

    try {
      if (isEditing && credential) {
        const payload: Record<string, unknown> = {}
        if (name.trim() !== credential.name) payload.name = name.trim()
        if (provider !== credential.provider) payload.provider = provider
        if (secret.trim()) payload.secret = secret.trim()
        if (provider === 'custom') {
          payload.metadata = { base_url: baseUrl.trim() }
        } else if (credential.metadata?.base_url) {
          payload.metadata = {}
        }
        await updateCredential.mutateAsync({ id: credential.id, data: payload as any })
        toast.success('Credential updated')
        onCredentialCreated(credential.id)
      } else {
        const payload: Record<string, unknown> = {
          project_id: projectId,
          provider,
          name: name.trim(),
          secret: secret.trim(),
        }
        if (provider === 'custom') {
          payload.metadata = { base_url: baseUrl.trim() }
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
          <p className="mt-1 text-xs text-muted">Credentials only store access. Models are created separately from this credential.</p>
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
            <p className="mt-1 text-xs text-muted">Use this for OpenAI-compatible gateways. The model slug is configured on the Models page.</p>
          </div>
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
