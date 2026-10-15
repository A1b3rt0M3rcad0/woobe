import { useEffect, useId, useState, type FormEvent } from 'react'
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
import { ProviderConnectionConfiguration } from './ProviderConnectionConfiguration'
import { ConfigurationReferenceSelector } from '@/features/projects/components/ConfigurationReferenceSelector'
import { useCredentials, useUpdateCredential } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { buildModelProviderCredentialMetadata, isOpenAICompatibleProvider, MODEL_PROVIDER_OPTIONS } from '@/features/provider-credentials/providers'

interface AddProviderCredentialModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  onCredentialCreated: (credentialId: string) => void
  credential?: ProviderCredential | null
}

export function AddProviderCredentialModal({ open, onClose, projectId, onCredentialCreated, credential }: AddProviderCredentialModalProps) {
  const id = useId()
  const credentialsQuery = useCredentials(projectId)
  const updateCredential = useUpdateCredential()
  const isEditing = Boolean(credential)
  const [provider, setProvider] = useState('openai')
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [configurationKey, setConfigurationKey] = useState('')
  const [saved, setSaved] = useState<ProviderCredential | null>(null)
  const [pending, setPending] = useState(false)
  useEffect(() => { if (open) { setSaved(null); setPending(false) } }, [open])
  const close = () => {
    if (pending || updateCredential.isPending) return
    if (saved) onCredentialCreated(saved.id)
    onClose()
  }

  useEffect(() => {
    if (!credential) return
    setProvider(credential.provider)
    setName(credential.name)
    setBaseUrl(String(credential.metadata?.base_url || ''))
    setConfigurationKey(credential.authentication?.fields.api_key.key ?? '')
  }, [credential, open])

  const handleEditSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!credential) return
    if (!name.trim()) return void toast.error('Name is required')
    if (credential.authentication && !configurationKey) return void toast.error('Select a declared configuration key')
    if (isOpenAICompatibleProvider(provider) && !baseUrl.trim()) return void toast.error('Base URL is required for OpenAI Compatible providers')
    try {
      await updateCredential.mutateAsync({
        id: credential.id,
        data: { name: name.trim(), provider, metadata: buildModelProviderCredentialMetadata(provider, baseUrl),
          ...(configurationKey && configurationKey !== credential.authentication?.fields.api_key.key
            ? { authentication: { type: 'api_key' as const, fields: { api_key: { source: 'project_environment' as const, key: configurationKey } } } } : {}) },
      })
      toast.success('Credential updated')
      onCredentialCreated(credential.id)
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update credential')
    }
  }

  return (
    <Dialog open={open} onClose={close} title={isEditing ? 'Edit Provider Credential' : saved ? 'Configure provider connection' : 'Connect provider'} className="max-w-2xl">
      {isEditing && credential ? (
        <form onSubmit={handleEditSubmit} className="grid gap-ui-md md:grid-cols-2">
          <Field>
            <FieldLabel htmlFor={`${id}-provider`}>Provider</FieldLabel>
            <Select id={`${id}-provider`} value={provider} onChange={(event) => setProvider(event.target.value)} options={MODEL_PROVIDER_OPTIONS.filter(option => option.value !== 'custom' || provider === 'custom')} />
          </Field>
          <Field>
            <FieldLabel htmlFor={`${id}-name`}>Connection name</FieldLabel>
            <Input id={`${id}-name`} value={name} onChange={(event) => setName(event.target.value)} placeholder="Provider connection" />
          </Field>
          {isOpenAICompatibleProvider(provider) ? (
            <Field>
              <FieldLabel htmlFor={`${id}-url`}>Base URL</FieldLabel>
              <Input id={`${id}-url`} value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" autoCapitalize="none" autoCorrect="off" spellCheck={false} />
            </Field>
          ) : null}
          {credential.authentication && <Field className="md:col-span-2"><FieldLabel>API key reference</FieldLabel><ConfigurationReferenceSelector projectId={projectId} value={configurationKey} onChange={setConfigurationKey} /></Field>}
          <Alert variant="info" className="md:col-span-2">
            <AlertDescription>{credential.authentication?.fields.api_key.source === 'legacy_configuration' ? 'This connection uses an explicit legacy mapping in the central store. Review its per-environment routes in Project → Environments; no automatic fallback is used.' : credential.authentication ? 'Values are managed in Project → Environments. Changing the reference or connection destination requires reviewing its use approvals.' : 'This connection uses the legacy credential contract. Review its migration in Project → Environments before changing how its value is stored.'}</AlertDescription>
          </Alert>
          <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-md md:col-span-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={updateCredential.isPending}>Cancel</Button>
            <Button type="submit" loading={updateCredential.isPending}>Save changes</Button>
          </div>
        </form>
      ) : saved ? (
        <div className="space-y-4"><div role="status"><p className="break-words text-sm font-medium">Connection saved: {saved.name}</p><p className="mt-1 text-sm leading-6 text-muted-foreground">Configure Draft access now, or let an authorized operator finish it in Environments.</p></div><ProviderConnectionConfiguration credential={saved} /><div className="flex justify-end border-t border-border pt-4"><Button onClick={close}>Done</Button></div></div>
      ) : (
        <ProviderCredentialCreateForm
          projectId={projectId}
          existingCredentials={credentialsQuery.data ?? []}
          onCreated={setSaved}
          onPendingChange={setPending}
          onCancel={close}
        />
      )}
    </Dialog>
  )
}
