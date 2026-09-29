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
  FieldOptional,
  FormActions,
  Input,
  TechnicalListItem,
} from '@woobe/ui'

import { useCreateCredential } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { ProviderSecretInput } from '@/features/provider-credentials/components/ProviderSecretInput'
import { buildModelProviderCredentialMetadata, isOpenAICompatibleProvider, MODEL_PROVIDER_LABELS, MODEL_PROVIDER_OPTIONS } from '@/features/provider-credentials/MODEL_PROVIDER_OPTIONS'

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

function buildModelProviderCredentialMetadata(provider: string, baseUrl: string): Record<string, string> {
  if (isOpenAICompatibleProvider(provider)) return { provider_family: 'openai', compatibility: 'compatible', base_url: baseUrl.trim(), model_discovery_strategy: 'openai_compatible_models' }
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
    return hostname || MODEL_PROVIDER_LABELS.openai_compatible
  } catch {
    return MODEL_PROVIDER_LABELS.custom
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
  const selectedProvider = useMemo(() => MODEL_PROVIDER_OPTIONS.find((item) => item.value === provider) || MODEL_PROVIDER_OPTIONS[0], [provider])

  useEffect(() => { onPendingChange?.(createCredential.isPending) }, [createCredential.isPending, onPendingChange])
  useEffect(() => {
    if (!isOpenAICompatibleProvider(provider)) {
      setBaseUrl('')
      setCustomName('')
    }
  }, [provider])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!secret.trim()) return void toast.error('API key is required')
    if (isOpenAICompatibleProvider(provider) && !baseUrl.trim()) return void toast.error('Base URL is required for OpenAI Compatible MODEL_PROVIDER_OPTIONS')
    const baseName = isOpenAICompatibleProvider(provider)
      ? customName.trim() || customCredentialBaseName(baseUrl)
      : MODEL_PROVIDER_LABELS[provider] || selectedProvider.label
    const name = uniqueCredentialName(baseName, existingCredentials)
    try {
      const credential = await createCredential.mutateAsync({
        project_id: projectId,
        provider,
        name,
        secret: secret.trim(),
        metadata: buildModelProviderCredentialMetadata(provider, baseUrl),
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
      <Field density="technical">
        <FieldLabel>Provider</FieldLabel>
        <div className="grid gap-ui-xs md:grid-cols-3">
          {MODEL_PROVIDER_OPTIONS.map((option) => {
            const selected = provider === option.value
            return (
              <TechnicalListItem
                key={option.value}
                label={option.label}
                description={option.description}
                descriptionVariant="technical"
                selected={selected}
                multiline
                density="technical"
                className="h-full items-start"
                trailing={selected ? <Check className="h-icon w-icon text-primary-light" /> : null}
                onClick={() => setProvider(option.value)}
              />
            )
          })}
        </div>
      </Field>

      {isOpenAICompatibleProvider(provider) ? (
        <div className="grid gap-ui-md sm:grid-cols-2">
          <Field density="technical">
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
          <Field density="technical">
            <FieldLabel>Connection name <FieldOptional /></FieldLabel>
            <Input value={customName} onChange={(event) => setCustomName(event.target.value)} placeholder="Defaults to the provider hostname" />
          </Field>
        </div>
      ) : null}

      <Field density="technical">
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
