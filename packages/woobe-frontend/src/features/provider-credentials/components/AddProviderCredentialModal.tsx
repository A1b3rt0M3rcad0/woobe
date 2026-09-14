import { useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import {
  Alert,
  AlertDescription,
  Button,
  Dialog,
  Field,
  FieldLabel,
  Input,
  Select,
} from '@woobe/ui'

import { ProviderCredentialCreateForm } from '@/features/provider-credentials/components/ProviderCredentialCreateForm'
import { useCredentials, useUpdateCredential } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'

const OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
const providers = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'custom', label: 'OpenAI Compatible' },
  { value: 'openrouter', label: 'OpenRouter' },
]

function buildCredentialMetadata(provider: string, baseUrl: string): Record<string, string> {
  if (provider === 'custom') return { provider_family: 'openai', compatibility: 'compatible', base_url: baseUrl.trim(), model_discovery_strategy: 'openai_compatible_models' }
  if (provider === 'openrouter') return { provider_family: 'openrouter', compatibility: 'native', base_url: OPENROUTER_BASE_URL, model_discovery_strategy: 'openai_compatible_models' }
  return { provider_family: 'openai', compatibility: 'native', model_discovery_strategy: 'openai_models' }
}

interface AddProviderCredentialModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  onCredentialCreated: (credentialId: string) => void
  credential?: ProviderCredential | null
}

export function AddProviderCredentialModal({ open, onClose, projectId, onCredentialCreated, credential }: AddProviderCredentialModalProps) {
  const credentialsQuery = useCredentials(projectId)
  const updateCredential = useUpdateCredential()
  const isEditing = Boolean(credential)
  const [provider, setProvider] = useState('openai')
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')

  useEffect(() => {
    if (!credential) return
    setProvider(credential.provider)
    setName(credential.name)
    setBaseUrl(String(credential.metadata?.base_url || ''))
  }, [credential, open])

  const handleEditSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!credential) return
    if (!name.trim()) return void toast.error('Name is required')
    if (provider === 'custom' && !baseUrl.trim()) return void toast.error('Base URL is required for OpenAI Compatible providers')
    try {
      await updateCredential.mutateAsync({
        id: credential.id,
        data: { name: name.trim(), provider, metadata: buildCredentialMetadata(provider, baseUrl) },
      })
      toast.success('Credential updated')
      onCredentialCreated(credential.id)
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update credential')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title={isEditing ? 'Edit Provider Credential' : 'Connect provider'}>
      {isEditing && credential ? (
        <form onSubmit={handleEditSubmit} className="grid gap-ui-md">
          <Field>
            <FieldLabel>Provider</FieldLabel>
            <Select value={provider} onChange={(event) => setProvider(event.target.value)} options={providers} />
          </Field>
          <Field>
            <FieldLabel>Connection name</FieldLabel>
            <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Provider connection" />
          </Field>
          {provider === 'custom' ? (
            <Field>
              <FieldLabel>Base URL</FieldLabel>
              <Input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" autoCapitalize="none" autoCorrect="off" spellCheck={false} />
            </Field>
          ) : null}
          <Alert variant="info">
            <AlertDescription>API keys are rotated from the credential details view so the replacement can be verified before the stored secret changes.</AlertDescription>
          </Alert>
          <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-md">
            <Button type="button" variant="outline" onClick={onClose} disabled={updateCredential.isPending}>Cancel</Button>
            <Button type="submit" loading={updateCredential.isPending}>Save changes</Button>
          </div>
        </form>
      ) : (
        <ProviderCredentialCreateForm
          projectId={projectId}
          existingCredentials={credentialsQuery.data ?? []}
          onCreated={(created) => {
            toast.success('Provider connected')
            onCredentialCreated(created.id)
            onClose()
          }}
          onCancel={onClose}
        />
      )}
    </Dialog>
  )
}
