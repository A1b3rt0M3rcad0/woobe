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
  { value: 'custom', label: 'Custom (OpenAI-compatible)' },
]

const defaultNames: Record<string, string> = {
  openai: 'OpenAI',
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
  const [modelName, setModelName] = useState('')

  useEffect(() => {
    if (credential) {
      setProvider(credential.provider)
      setName(credential.name)
      setSecret('')
      const meta = credential.metadata || {}
      setBaseUrl(meta.base_url || '')
      setModelName(meta.model || meta.model_name || '')
    } else {
      setProvider('openai')
      setName(defaultNames.openai)
      setSecret('')
      setBaseUrl('')
      setModelName('')
    }
  }, [credential, open])

  useEffect(() => {
    if (isEditing) return
    setName(defaultNames[provider] || '')
    if (provider !== 'custom') {
      setBaseUrl('')
      setModelName('')
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
    if (provider !== 'openai' && provider !== 'custom') {
      toast.error('This provider is not supported in the MVP')
      return
    }
    if (provider === 'custom' && !baseUrl.trim()) {
      toast.error('Base URL is required for custom providers')
      return
    }
    if (provider === 'custom' && !modelName.trim()) {
      toast.error('Model name is required for custom providers')
      return
    }

    try {
      if (isEditing && credential) {
        const payload: Record<string, unknown> = {}
        if (name.trim() !== credential.name) payload.name = name.trim()
        if (provider !== credential.provider) payload.provider = provider
        if (secret.trim()) payload.secret = secret.trim()
        if (provider === 'custom') {
          const meta: Record<string, string> = {}
          if (baseUrl.trim()) meta.base_url = baseUrl.trim()
          if (modelName.trim()) meta.model = modelName.trim()
          if (Object.keys(meta).length > 0) payload.metadata = meta
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
          payload.metadata = {
            base_url: baseUrl.trim(),
            model: modelName.trim(),
          }
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
          <label className="block text-sm font-medium text-muted mb-1">Provider</label>
          <Select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            options={providers}
          />
          <p className="mt-1 text-xs text-muted">The MVP supports OpenAI and OpenAI-compatible providers only.</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Name</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My API Key"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted mb-1">API Key</label>
          <Input
            type="password"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            placeholder={isEditing ? 'Leave blank to keep current' : (provider === 'openai' ? 'sk-...' : 'Paste your API key')}
          />
        </div>
        {provider === 'custom' && (
          <>
            <div>
              <label className="block text-sm font-medium text-muted mb-1">Base URL</label>
              <Input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.example.com/v1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-muted mb-1">Model Name</label>
              <Input
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder="e.g. my-model-name"
              />
            </div>
          </>
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
