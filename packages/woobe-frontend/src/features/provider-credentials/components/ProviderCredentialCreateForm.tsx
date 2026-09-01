import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Check } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useCreateCredential } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { ProviderSecretInput } from '@/features/provider-credentials/components/ProviderSecretInput'

const OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'

const providers = [
  {
    value: 'openai',
    label: 'OpenAI',
    description: 'Use models available from your OpenAI account.',
  },
  {
    value: 'openrouter',
    label: 'OpenRouter',
    description: 'Access multiple generation and embedding providers through one connection.',
  },
  {
    value: 'custom',
    label: 'OpenAI Compatible',
    description: 'Connect a provider or gateway that exposes an OpenAI-compatible API.',
  },
]

const providerNames: Record<string, string> = {
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
  custom: 'OpenAI Compatible',
}

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
  if (provider === 'custom') {
    return {
      provider_family: 'openai',
      compatibility: 'compatible',
      base_url: baseUrl.trim(),
      model_discovery_strategy: 'openai_compatible_models',
    }
  }
  if (provider === 'openrouter') {
    return {
      provider_family: 'openrouter',
      compatibility: 'native',
      base_url: OPENROUTER_BASE_URL,
      model_discovery_strategy: 'openrouter_models',
    }
  }
  return {
    provider_family: 'openai',
    compatibility: 'native',
    model_discovery_strategy: 'openai_models',
  }
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

  const selectedProvider = useMemo(
    () => providers.find((item) => item.value === provider) || providers[0],
    [provider],
  )

  useEffect(() => {
    onPendingChange?.(createCredential.isPending)
  }, [createCredential.isPending, onPendingChange])

  useEffect(() => {
    if (provider !== 'custom') {
      setBaseUrl('')
      setCustomName('')
    }
  }, [provider])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!secret.trim()) return toast.error('API key is required')
    if (provider === 'custom' && !baseUrl.trim()) return toast.error('Base URL is required for OpenAI Compatible providers')

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
    <form id={formId} onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="mb-2 block text-sm font-medium text-muted">Provider</label>
        <div className="grid gap-2 sm:grid-cols-3">
          {providers.map((option) => {
            const selected = provider === option.value
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setProvider(option.value)}
                className={`rounded-xl border p-3 text-left transition-colors ${selected ? 'border-primary/55 bg-primary/8' : 'border-border/85 bg-background/55 hover:border-primary/30'}`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-white">{option.label}</span>
                  {selected && <Check className="h-4 w-4 text-primary-light" />}
                </span>
                <span className="mt-2 block text-xs leading-5 text-muted">{option.description}</span>
              </button>
            )
          })}
        </div>
      </div>

      {provider === 'custom' && (
        <>
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Base URL</label>
            <Input
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="https://api.example.com/v1"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Connection name <span className="font-normal text-muted/70">(optional)</span></label>
            <Input
              value={customName}
              onChange={(event) => setCustomName(event.target.value)}
              placeholder="Defaults to the provider hostname"
            />
          </div>
        </>
      )}

      <div>
        <label className="mb-1 block text-sm font-medium text-muted">API key</label>
        <ProviderSecretInput value={secret} onChange={setSecret} />
        <p className="mt-1 text-xs text-muted">Stored as a Project credential and never used as a login password.</p>
      </div>

      {provider === 'openrouter' && (
        <p className="rounded-lg border border-border bg-background/60 p-3 text-xs text-muted">The OpenRouter endpoint is configured automatically.</p>
      )}

      {showActions && (
        <div className="flex justify-end gap-2 pt-2">
          {onCancel && <Button type="button" variant="outline" onClick={onCancel} disabled={createCredential.isPending}>Cancel</Button>}
          <Button type="submit" loading={createCredential.isPending}>{submitLabel}</Button>
        </div>
      )}
    </form>
  )
}
