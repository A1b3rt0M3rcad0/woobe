import { useEffect, useId, useMemo, useState, type FormEvent } from 'react'
import { Button, Field, FieldDescription, FieldLabel, FieldError, FormActions, Input } from '@woobe/ui'
import { useCreateCredential } from '../hooks'
import type { ProviderCredential } from '../types'
import { ConfigurationReferenceSelector } from '@/features/projects/components/ConfigurationReferenceSelector'
import { buildModelProviderCredentialMetadata, isOpenAICompatibleProvider, MODEL_PROVIDER_LABELS, MODEL_PROVIDER_OPTIONS } from '../providers'

interface ProviderCredentialCreateFormProps {
  projectId: string
  existingCredentials: ProviderCredential[]
  onCreated: (credential: ProviderCredential) => void
  formId?: string
  submitLabel?: string
  showActions?: boolean
  onCancel?: () => void
  onPendingChange?: (pending: boolean) => void
}
function uniqueCredentialName(base: string, credentials: ProviderCredential[]) {
  const names = new Set(credentials.map(item => item.name.trim().toLowerCase()))
  let name = base, suffix = 2
  while (names.has(name.toLowerCase())) name = `${base} ${suffix++}`
  return name
}
export function ProviderCredentialCreateForm({ projectId, existingCredentials, onCreated, formId, submitLabel = 'Save connection', showActions = true, onCancel, onPendingChange }: ProviderCredentialCreateFormProps) {
  const id = useId()
  const create = useCreateCredential()
  const [provider, setProvider] = useState('openai')
  const [configurationKey, setConfigurationKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [keyError, setKeyError] = useState('')
  const [urlError, setUrlError] = useState('')
  const compatible = isOpenAICompatibleProvider(provider)
  const defaultName = useMemo(() => {
    if (compatible && baseUrl.trim()) { try { return new URL(baseUrl).hostname } catch { /* Use provider label until valid. */ } }
    return MODEL_PROVIDER_LABELS[provider]
  }, [provider, compatible, baseUrl])
  useEffect(() => { onPendingChange?.(create.isPending) }, [create.isPending, onPendingChange])
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError(''); setKeyError(''); setUrlError('')
    const form = event.currentTarget as HTMLFormElement
    if (!configurationKey) { setKeyError('Choose a secret key or declare a new one.'); form.querySelector<HTMLSelectElement>('select')?.focus(); return }
    if (compatible) {
      try { const url = new URL(baseUrl.trim()); if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.hash) throw new Error() }
      catch { setUrlError('Enter a complete HTTP or HTTPS endpoint, such as https://api.example.com/v1.'); (form.elements.namedItem(`${id}-url`) as HTMLInputElement | null)?.focus(); return }
    }
    try {
      const created = await create.mutateAsync({ project_id: projectId, provider, name: name.trim() || uniqueCredentialName(defaultName, existingCredentials),
        authentication: { type: 'api_key', fields: { api_key: { source: 'project_environment', key: configurationKey } } },
        metadata: buildModelProviderCredentialMetadata(provider, baseUrl) })
      // The next screen unmounts this form before the mutation's final effect.
      // Clear the parent's busy state before handing over the saved connection.
      onPendingChange?.(false)
      onCreated(created)
    } catch { setError('The connection was not saved. Check your permissions and connection details, then try again.') }
  }
  return <form id={formId} onSubmit={submit} noValidate className="grid gap-5">
    <p className="text-sm leading-6 text-muted-foreground">Choose a provider and the key it will use. After saving, configure the API key value and destination access for Draft.</p>
    <fieldset disabled={create.isPending} className="min-w-0 space-y-2"><legend className="mb-2 text-sm font-medium">Provider</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {MODEL_PROVIDER_OPTIONS.filter(option => option.value !== 'custom').map(option => <label key={option.value} className="min-w-0 cursor-pointer">
          <input type="radio" name={`${id}-provider`} value={option.value} checked={provider === option.value} onChange={() => { setProvider(option.value); setUrlError('') }} className="peer sr-only" />
          <span className={`block h-full rounded-control border p-3 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary ${provider === option.value ? 'border-primary bg-primary/5' : 'border-border bg-background/30'}`}><span className="block text-sm font-medium text-foreground">{option.label}</span><span className="mt-1 block text-xs leading-5 text-muted-foreground">{option.description}</span></span>
        </label>)}
      </div>
    </fieldset>
    {compatible && <Field><FieldLabel htmlFor={`${id}-url`}>Base URL</FieldLabel><Input id={`${id}-url`} value={baseUrl} onChange={event => { setBaseUrl(event.target.value); setUrlError('') }} aria-invalid={!!urlError} aria-describedby={urlError ? `${id}-url-error` : undefined} placeholder="https://api.example.com/v1" autoCapitalize="none" autoCorrect="off" spellCheck={false} disabled={create.isPending} />{urlError && <FieldError id={`${id}-url-error`}>{urlError}</FieldError>}</Field>}
    <Field><FieldLabel htmlFor={`${id}-name`}>Connection name <span className="font-normal text-muted-foreground">(optional)</span></FieldLabel><Input id={`${id}-name`} value={name} onChange={event => setName(event.target.value)} placeholder={defaultName} disabled={create.isPending} /><FieldDescription className="text-sm leading-5">Use a name your team will recognize, such as “Support provider”.</FieldDescription></Field>
    <Field><FieldLabel>API key reference</FieldLabel><ConfigurationReferenceSelector disabled={create.isPending} projectId={projectId} value={configurationKey} suggestedKey={`${provider.toUpperCase()}_API_KEY`} onChange={value => { setConfigurationKey(value); setKeyError('') }} /><FieldDescription className="text-sm leading-5">Select a key name, not the API key value. “Declare key” creates a name you can configure next.</FieldDescription>{keyError && <FieldError role="alert">{keyError}</FieldError>}</Field>
    <p className="text-xs leading-5 text-muted-foreground">Saving creates a Project connection. It does not test access, discover models or run an Agent.</p>
    {error && <p role="alert" className="text-sm text-error">{error}</p>}
    {showActions && <FormActions>{onCancel && <Button type="button" variant="outline" onClick={onCancel} disabled={create.isPending}>Cancel</Button>}<Button type="submit" loading={create.isPending}>{submitLabel}</Button></FormActions>}
  </form>
}
