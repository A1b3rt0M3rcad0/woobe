import { useState, useEffect } from 'react'
import { useCreateCredential } from '@/features/provider-credentials/hooks'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { toast } from 'sonner'

const providers = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google' },
  { value: 'custom', label: 'Custom' },
]

const defaultNames: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google AI',
  custom: 'Custom Provider',
}

interface AddProviderCredentialModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  onCredentialCreated: (credentialId: string) => void
}

export function AddProviderCredentialModal({ open, onClose, projectId, onCredentialCreated }: AddProviderCredentialModalProps) {
  const createCredential = useCreateCredential()
  const [provider, setProvider] = useState('openai')
  const [name, setName] = useState(defaultNames.openai)
  const [secret, setSecret] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [modelName, setModelName] = useState('')

  useEffect(() => {
    setName(defaultNames[provider] || '')
    if (provider !== 'custom') {
      setBaseUrl('')
      setModelName('')
    }
  }, [provider])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !secret.trim()) {
      toast.error('Name and API key are required')
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
      setProvider('openai')
      setName(defaultNames.openai)
      setSecret('')
      setBaseUrl('')
      setModelName('')
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create credential')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Add Provider Credential">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Provider</label>
          <Select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            options={providers}
          />
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
            placeholder={provider === 'openai' ? 'sk-...' : 'Paste your API key'}
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
          <Button type="submit" loading={createCredential.isPending}>Save</Button>
        </div>
      </form>
    </Dialog>
  )
}
