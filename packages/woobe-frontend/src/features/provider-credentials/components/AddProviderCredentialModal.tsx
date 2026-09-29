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
import { buildModelProviderCredentialMetadata, isOpenAICompatibleProvider, MODEL_PROVIDER_OPTIONS } from '@/features/provider-credentials/MODEL_PROVIDER_OPTIONS'

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
    if (isOpenAICompatibleProvider(provider) && !baseUrl.trim()) return void toast.error('Base URL is required for OpenAI Compatible MODEL_PROVIDER_OPTIONS')
    try {
      await updateCredential.mutateAsync({
        id: credential.id,
        data: { name: name.trim(), provider, metadata: buildModelProviderCredentialMetadata(provider, baseUrl) },
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
            <Select value={provider} onChange={(event) => setProvider(event.target.value)} options={MODEL_PROVIDER_OPTIONS} />
          </Field>
          <Field>
            <FieldLabel>Connection name</FieldLabel>
            <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Provider connection" />
          </Field>
          {isOpenAICompatibleProvider(provider) ? (
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
