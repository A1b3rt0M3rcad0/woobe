import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Check } from 'lucide-react'
import { toast } from 'sonner'
import {
  Alert,
  AlertDescription,
  Button,
  Field,
  FieldDescription,
  FieldLabel,
  FormActions,
  Input,
  TechnicalListItem,
} from '@woobe/ui'

import { useCreateCredential } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { ProviderSecretInput } from '@/features/provider-credentials/components/ProviderSecretInput'

const OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
const providers = [
  { value: 'openai', label: 'OpenAI', description: 'Native OpenAI models.' },
  { value: 'openrouter', label: 'OpenRouter', description: 'Multi-provider gateway.' },
  { value: 'custom', label: 'OpenAI Compatible', description: 'Custom OpenAI-compatible endpoint.' },
]
const providerNames: Record<string, string> = { openai: 'OpenAI', openrouter: 'OpenRouter', custom: 'OpenAI Compatible' }

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

function buildCredentialMetadata(provider: string, baseUrl: string): Record<string, string> {
  if (provider === 'custom') return { provider_family: 'openai', compatibility: 'compatible', base_url: baseUrl.trim(), model_discovery_strategy: 'openai_compatible_models' }
  if (provider === 'openrouter') return { provider_family: 'openrouter', compatibility: 'native', base_url: OPENROUTER_BASE_URL, model_discovery_strategy: 'openrouter_models' }
  return { provider_family: 'openai', compatibility: 'native', model_discovery_strategy: 'openai_models' }
}

function uniqueCredentialName(baseName: string, credentials: ProviderCredential[]) {
  const normalizedNames = new Set(credentials.map((credential) => credential.name.trim().toLowerCase()))
  if (!normalizedNames.has(baseName.trim().toLowerCase())) return baseName
  let suffix = 2
  while (normalizedNames.has(`${baseName} ${suffix}`.toLowerCase())) suffix += 1
  return `${baseName} ${suffix}`
}

function customCredentialBaseName(baseUrl: string) {
  try {
    const hostname = new URL(baseUrl.trim()).hostname
    return hostname || providerNames.custom
  } catch {
    return providerNames.custom
  }
}

export function ProviderCredentialCreateForm({
  projectId,
  existingCredentials,
  onCreated,
  formId,
  submitLabel = 'Connect',
  showActions = true,
  onCancel,
  onPendingChange,
}: ProviderCredentialCreateFormProps) {
  const createCredential = useCreateCredential()
  const [provider, setProvider] = useState('openai')
  const [secret, setSecret] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [customName, setCustomName] = useState('')
  const selectedProvider = useMemo(() => providers.find((item) => item.value === provider) || providers[0], [provider])

  useEffect(() => { onPendingChange?.(createCredential.isPending) }, [createCredential.isPending, onPendingChange])
  useEffect(() => {
    if (provider !== 'custom') {
      setBaseUrl('')
      setCustomName('')
    }
  }, [provider])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!secret.trim()) return void toast.error('API key is required')
    if (provider === 'custom' && !baseUrl.trim()) return void toast.error('Base URL is required for OpenAI Compatible providers')
    const baseName = provider === 'custom'
      ? customName.trim() || customCredentialBaseName(baseUrl)
      : providerNames[provider] || selectedProvider.label
    const name = uniqueCredentialName(baseName, existingCredentials)
    try {
      const credential = await createCredential.mutateAsync({
        project_id: projectId,
        provider,
        name,
        secret: secret.trim(),
        metadata: buildCredentialMetadata(provider, baseUrl),
      })
      setSecret('')
      setBaseUrl('')
      setCustomName('')
      onCreated(credential)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect provider')
    }
  }

  return (
    <form id={formId} onSubmit={handleSubmit} className="grid gap-ui-md">
      <Field>
        <FieldLabel>Provider</FieldLabel>
        <div className="grid gap-ui-xs md:grid-cols-3">
          {providers.map((option) => {
            const selected = provider === option.value
            return (
              <TechnicalListItem
                key={option.value}
                label={option.label}
                description={option.description}
                selected={selected}
                multiline
                density="compact"
                className="h-full items-start"
                trailing={selected ? <Check className="h-icon w-icon text-primary-light" /> : null}
                onClick={() => setProvider(option.value)}
              />
            )
          })}
        </div>
      </Field>

      {provider === 'custom' ? (
        <div className="grid gap-ui-md sm:grid-cols-2">
          <Field>
            <FieldLabel>Base URL</FieldLabel>
            <Input
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="https://api.example.com/v1"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
            />
          </Field>
          <Field>
            <FieldLabel>Connection name <span className="font-normal text-muted-foreground">(optional)</span></FieldLabel>
            <Input value={customName} onChange={(event) => setCustomName(event.target.value)} placeholder="Defaults to the provider hostname" />
          </Field>
        </div>
      ) : null}

      <Field>
        <FieldLabel>API key</FieldLabel>
        <ProviderSecretInput value={secret} onChange={setSecret} />
        <FieldDescription>Stored as a Project credential and never used as a login password.</FieldDescription>
      </Field>

      {provider === 'openrouter' ? (
        <Alert variant="info">
          <AlertDescription>The OpenRouter endpoint is configured automatically.</AlertDescription>
        </Alert>
      ) : null}

      {showActions ? (
        <FormActions>
          {onCancel ? (
            <Button type="button" variant="outline" onClick={onCancel} disabled={createCredential.isPending}>Cancel</Button>
          ) : null}
          <Button type="submit" loading={createCredential.isPending}>{submitLabel}</Button>
        </FormActions>
      ) : null}
    </form>
  )
}
