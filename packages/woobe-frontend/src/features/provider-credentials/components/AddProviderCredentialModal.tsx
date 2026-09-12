import { useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { Alert, AlertDescription, Field, FieldLabel } from '@woobe/ui'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { ProviderCredentialCreateForm } from '@/features/provider-credentials/components/ProviderCredentialCreateForm'
import { useCredentials, useUpdateCredential } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'

const OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
const providers = [{ value: 'openai', label: 'OpenAI' }, { value: 'custom', label: 'OpenAI Compatible' }, { value: 'openrouter', label: 'OpenRouter' }]
function buildCredentialMetadata(provider: string, baseUrl: string): Record<string, string> {
  if (provider === 'custom') return { provider_family: 'openai', compatibility: 'compatible', base_url: baseUrl.trim(), model_discovery_strategy: 'openai_compatible_models' }
  if (provider === 'openrouter') return { provider_family: 'openrouter', compatibility: 'native', base_url: OPENROUTER_BASE_URL, model_discovery_strategy: 'openrouter_models' }
  return { provider_family: 'openai', compatibility: 'native', model_discovery_strategy: 'openai_models' }
}

interface AddProviderCredentialModalProps { open: boolean; onClose: () => void; projectId: string; onCredentialCreated: (credentialId: string) => void; credential?: ProviderCredential | null }

export function AddProviderCredentialModal({ open, onClose, projectId, onCredentialCreated, credential }: AddProviderCredentialModalProps) {
  const credentialsQuery = useCredentials(projectId)
  const updateCredential = useUpdateCredential()
  const isEditing = Boolean(credential)
  const [provider, setProvider] = useState('openai')
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')

  useEffect(() => { if (!credential) return; setProvider(credential.provider); setName(credential.name); setBaseUrl(String(credential.metadata?.base_url || '')) }, [credential, open])

  const handleEditSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!credential) return
    if (!name.trim()) return toast.error('Name is required')
    if (provider === 'custom' && !baseUrl.trim()) return toast.error('Base URL is required for OpenAI Compatible providers')
    try {
      await updateCredential.mutateAsync({ id: credential.id, data: { name: name.trim(), provider, metadata: buildCredentialMetadata(provider, baseUrl) } })
      toast.success('Credential updated'); onCredentialCreated(credential.id); onClose()
    } catch (err) { toast.error(err instanceof Error ? err.message : 'Failed to update credential') }
  }

  return <Dialog open={open} onClose={onClose} title={isEditing ? 'Edit Provider Credential' : 'Connect provider'} className="max-w-2xl">
    {isEditing && credential ? <form onSubmit={handleEditSubmit} className="space-y-3"><Field><FieldLabel>Provider</FieldLabel><Select value={provider} onChange={(event) => setProvider(event.target.value)} options={providers} /></Field><Field><FieldLabel>Connection name</FieldLabel><Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Provider connection" /></Field>{provider === 'custom' ? <Field><FieldLabel>Base URL</FieldLabel><Input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" autoCapitalize="none" autoCorrect="off" spellCheck={false} /></Field> : null}<Alert><AlertDescription>API keys are rotated from the credential details view so the replacement can be verified before the stored secret changes.</AlertDescription></Alert><div className="flex justify-end gap-2 border-t border-border pt-3"><Button type="button" variant="outline" onClick={onClose} disabled={updateCredential.isPending}>Cancel</Button><Button type="submit" loading={updateCredential.isPending}>Save changes</Button></div></form> : <ProviderCredentialCreateForm projectId={projectId} existingCredentials={credentialsQuery.data ?? []} onCreated={(created) => { toast.success('Provider connected'); onCredentialCreated(created.id); onClose() }} onCancel={onClose} />}
  </Dialog>
}
