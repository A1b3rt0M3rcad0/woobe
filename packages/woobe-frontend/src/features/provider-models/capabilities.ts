import { providerModelSpec } from './modelSpec'
import type { ProviderModel } from './types'

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function firstPositiveInteger(...values: unknown[]): number | null {
  for (const value of values) {
    const parsed = typeof value === 'number'
      ? value
      : typeof value === 'string' && /^\d+$/.test(value.trim())
        ? Number(value)
        : Number.NaN
    if (Number.isSafeInteger(parsed) && parsed > 0) return parsed
  }
  return null
}

// Keep the same explicit sources and precedence as shared/contracts/llm_cost.py.
export function providerModelCapabilities(model: ProviderModel | null | undefined) {
  const spec = providerModelSpec(model)
  const metadata = record(model?.metadata)
  const catalog = record(metadata.catalog)
  const capabilities = record(metadata.capabilities)
  const raw = record(metadata.provider_model_raw)
  const rawTopProvider = record(raw.top_provider)
  return {
    contextWindow: firstPositiveInteger(
      spec?.limits.context_window,
      spec?.limits.max_input_tokens,
      metadata.context_window,
      metadata.context_length,
      metadata.max_context_tokens,
      metadata.max_input_tokens,
      catalog.context_window,
      catalog.context_length,
      catalog.max_context_tokens,
      catalog.max_input_tokens,
      raw.context_window,
      raw.context_length,
      raw.max_context_tokens,
      raw.max_input_tokens,
      rawTopProvider.context_length,
    ),
    maxOutputTokens: firstPositiveInteger(
      spec?.limits.max_output_tokens,
      metadata.max_output_tokens,
      capabilities.max_output_tokens,
      catalog.max_output_tokens,
      raw.max_output_tokens,
      raw.max_completion_tokens,
      rawTopProvider.max_completion_tokens,
    ),
  }
}
