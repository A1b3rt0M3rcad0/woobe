import type { ProviderModel } from './types'

export interface NormalizedFrontendModelSpec {
  specVersion: number | null
  provider: string | null
  modelId: string | null
  displayName: string | null
  modelType: string | null
  operations: string[]
  inputModalities: string[]
  outputModalities: string[]
  interaction: {
    mode: string | null
    supportsConversation: boolean | null
    supportsHistory: boolean | null
    supportsSystemInstruction: boolean | null
    supportsContextInjection: boolean | null
    supportsBatch: boolean | null
    supportsRealtime: boolean | null
  }
  capabilities: Record<string, boolean | null>
  limits: Record<string, number | null>
  source: string | null
  defaultModelStrategy: string | null
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function stringValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function booleanValue(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null
}

function positiveInteger(value: unknown): number | null {
  if (typeof value === 'boolean' || value == null) return null
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return Array.from(new Set(
    value
      .filter((item): item is string => typeof item === 'string' && Boolean(item.trim()))
      .map((item) => item.trim()),
  ))
}

function normalizedCapabilities(value: unknown): Record<string, boolean | null> {
  const capabilities: Record<string, boolean | null> = {}
  for (const [name, raw] of Object.entries(record(value))) {
    if (typeof raw === 'boolean') {
      capabilities[name] = raw
      continue
    }
    const item = record(raw)
    capabilities[name] = booleanValue(item.supported)
  }
  return capabilities
}

export function normalizeModelSpec(value: unknown): NormalizedFrontendModelSpec | null {
  const spec = record(value)
  const operations = stringList(spec.operations)
  const inputModalities = stringList(spec.input_modalities)
  const outputModalities = stringList(spec.output_modalities)

  if (!operations.length && !inputModalities.length && !outputModalities.length) return null

  const interaction = record(spec.interaction)
  const limits = record(spec.limits)

  return {
    specVersion: positiveInteger(spec.spec_version),
    provider: stringValue(spec.provider),
    modelId: stringValue(spec.model_id),
    displayName: stringValue(spec.display_name),
    modelType: stringValue(spec.model_type),
    operations,
    inputModalities,
    outputModalities,
    interaction: {
      mode: stringValue(interaction.mode),
      supportsConversation: booleanValue(interaction.supports_conversation),
      supportsHistory: booleanValue(interaction.supports_history),
      supportsSystemInstruction: booleanValue(interaction.supports_system_instruction),
      supportsContextInjection: booleanValue(interaction.supports_context_injection),
      supportsBatch: booleanValue(interaction.supports_batch),
      supportsRealtime: booleanValue(interaction.supports_realtime),
    },
    capabilities: normalizedCapabilities(spec.capabilities),
    limits: {
      context_window: positiveInteger(limits.context_window),
      max_input_tokens: positiveInteger(limits.max_input_tokens),
      max_output_tokens: positiveInteger(limits.max_output_tokens),
      max_batch_size: positiveInteger(limits.max_batch_size),
      max_input_bytes: positiveInteger(limits.max_input_bytes),
      max_output_bytes: positiveInteger(limits.max_output_bytes),
    },
    source: stringValue(spec.source),
    defaultModelStrategy: stringValue(spec.default_model_strategy),
  }
}

export function providerModelSpec(model: ProviderModel | null | undefined): NormalizedFrontendModelSpec | null {
  return normalizeModelSpec(model?.spec)
}

export function catalogModelSpec(raw: unknown): NormalizedFrontendModelSpec | null {
  const payload = record(raw)
  return normalizeModelSpec(payload.woobe_model_spec)
}

export function modelCapabilityState(
  spec: NormalizedFrontendModelSpec | null,
  capability: string,
): boolean | null {
  if (!spec || !Object.prototype.hasOwnProperty.call(spec.capabilities, capability)) return null
  return spec.capabilities[capability] ?? null
}
