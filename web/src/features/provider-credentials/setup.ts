export const OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'

export const providerOptions = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'custom', label: 'OpenAI Compatible' },
  { value: 'openrouter', label: 'OpenRouter' },
]

export const defaultCredentialNames: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible Provider',
  openrouter: 'OpenRouter',
}

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible',
  openrouter: 'OpenRouter',
}

export function providerLabel(provider?: string | null) {
  if (!provider) return 'Provider'
  return providerLabels[provider] || provider
}

export function buildCredentialMetadata(provider: string, baseUrl: string): Record<string, string> {
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
