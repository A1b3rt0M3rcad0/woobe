export const MODEL_PROVIDER_OPTIONS = [
  { value: 'openai', label: 'OpenAI', description: 'Native OpenAI models.' },
  { value: 'anthropic', label: 'Anthropic', description: 'Native Anthropic Claude models.' },
  { value: 'deepseek', label: 'DeepSeek', description: 'Native DeepSeek models.' },
  { value: 'openrouter', label: 'OpenRouter', description: 'Multi-provider gateway.' },
  { value: 'openai_compatible', label: 'OpenAI Compatible', description: 'Custom OpenAI-compatible endpoint.' },
  { value: 'custom', label: 'OpenAI Compatible (legacy)', description: 'Legacy alias for an OpenAI-compatible endpoint.' },
] as const

export const MODEL_PROVIDER_LABELS: Record<string, string> = Object.fromEntries(
  MODEL_PROVIDER_OPTIONS.map((provider) => [provider.value, provider.label]),
)

export function isOpenAICompatibleProvider(provider: string) {
  return provider === 'openai_compatible' || provider === 'custom'
}

export function modelProviderLabel(provider?: string | null) {
  return provider ? MODEL_PROVIDER_LABELS[provider] || provider : 'Unknown provider'
}

export function buildModelProviderCredentialMetadata(
  provider: string,
  baseUrl: string,
): Record<string, string> {
  if (isOpenAICompatibleProvider(provider)) {
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
      base_url: 'https://openrouter.ai/api/v1',
      model_discovery_strategy: 'openrouter_models',
    }
  }
  if (provider === 'anthropic') {
    return {
      provider_family: 'anthropic',
      compatibility: 'native',
      model_discovery_strategy: 'anthropic_models',
    }
  }
  if (provider === 'deepseek') {
    return {
      provider_family: 'deepseek',
      compatibility: 'native',
      model_discovery_strategy: 'deepseek_models',
    }
  }
  return {
    provider_family: 'openai',
    compatibility: 'native',
    model_discovery_strategy: 'openai_models',
  }
}
