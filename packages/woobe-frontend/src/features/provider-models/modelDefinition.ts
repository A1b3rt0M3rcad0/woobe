import type { AvailableProviderModel, CreateProviderModelRequest, ProviderModel } from './types'

export function discoveredModelSpec(model?: AvailableProviderModel | null) {
  return model?.model_spec ?? model?.raw?.woobe_model_spec ?? null
}

export function effectiveModelPricing(model?: ProviderModel | null): Record<string, any> {
  return model?.spec ? model.spec.pricing ?? {} : model?.metadata?.pricing ?? model?.metadata ?? {}
}

export function isAgentModel(model: ProviderModel): boolean {
  if (model.spec) return Boolean(model.spec.operations?.includes('language.generate')
    && model.spec.output_modalities?.includes('text') && model.spec.interaction?.supports_conversation === true)
  const kind = model.model_type || model.metadata?.capability || model.metadata?.type
  if (kind) return ['language', 'generation', 'chat'].includes(kind)
  // Compatibility only for historical records without a normalized definition.
  return !`${model.name} ${model.model}`.toLowerCase().includes('embed')
}

interface DefinitionInput {
  projectId: string
  credentialId: string
  name: string
  modelId: string
  existing?: ProviderModel | null
  catalog?: AvailableProviderModel | null
  metadata?: Record<string, any>
  modelType?: string
  inheritCatalog?: boolean
}

export function buildProviderModelDefinition(input: DefinitionInput): CreateProviderModelRequest {
  const modelId = input.modelId.trim()
  const sameIdentity = !input.existing || (input.existing.model === modelId && input.existing.provider_credential_id === input.credentialId)
  const catalog = input.catalog?.id === modelId ? input.catalog : null
  const spec = discoveredModelSpec(catalog)
  const metadata = structuredClone(input.metadata ?? {})
  if (!sameIdentity || (input.catalog && !catalog)) {
    for (const key of ['model_spec_baseline', 'model_spec_overrides', 'model_spec', 'provider_model_raw', 'catalog']) delete metadata[key]
  }
  if (catalog && !spec) throw new Error('This catalog item requires a manual ModelSpec before it can be installed')
  const baseline = spec ?? (sameIdentity ? input.existing?.metadata?.model_spec_baseline ?? input.existing?.spec : null)
  const current = spec ?? (sameIdentity ? input.existing?.spec : null)
  const overrides: Record<string, Record<string, any>> = {}
  if (input.inheritCatalog) for (const [group, fields] of Object.entries(input.existing?.metadata?.model_spec_overrides ?? {})) {
    overrides[group] = Object.fromEntries(Object.keys(fields as object).map(key => [key, { action: 'inherit' }]))
  }
  const compare = (group: string, key: string, value: unknown, old: unknown, inherited: unknown) => {
    if (value === undefined || (value === old && !spec && !input.inheritCatalog)) return
    const hadOverride = Object.prototype.hasOwnProperty.call(input.existing?.metadata?.model_spec_overrides?.[group] ?? {}, key)
    const inheritedValue = inherited ?? (group === 'capabilities' ? 'unknown' : key === 'currency' ? 'USD' : key === 'billing_unit' ? 'per_1m_tokens' : null)
    if (input.inheritCatalog && value === inheritedValue) return
    if ((value === null || value === inherited) && !hadOverride) return
    overrides[group] ??= {}
    if (value === null || value === inherited) overrides[group][key] = { action: 'inherit' }
    else overrides[group][key] = value
  }
  for (const [old, key] of Object.entries({ supports_tools: 'tool_calling', supports_json: 'structured_output', supports_streaming: 'streaming' })) {
    const value = metadata.capabilities?.[old]
    if (value === null && current?.capabilities?.[key] === undefined) continue
    compare('capabilities', key, value === null ? 'unknown' : value, current?.capabilities?.[key]?.supported, baseline?.capabilities?.[key]?.supported)
  }
  for (const key of ['context_window', 'max_output_tokens']) {
    const value = metadata[key]
    if (value !== undefined && value !== null && (!Number.isSafeInteger(value) || value <= 0)) throw new Error('Model limits must be positive integers')
    compare('limits', key, value, current?.limits?.[key], baseline?.limits?.[key])
    delete metadata[key]
  }
  for (const key of ['input_cost_per_1m_tokens', 'output_cost_per_1m_tokens', 'currency', 'billing_unit']) {
    const value = metadata.pricing?.[key]
    if (key.endsWith('_tokens') && value != null && (typeof value !== 'number' || !Number.isFinite(value) || value < 0)) throw new Error('Model prices must be finite nonnegative numbers')
    compare('pricing', key, value, current?.pricing?.[key], baseline?.pricing?.[key])
  }
  delete metadata.capabilities
  delete metadata.pricing
  if (baseline) metadata.model_spec_baseline = baseline
  metadata.model_spec_overrides = overrides
  if (catalog) metadata.provider_model_raw = catalog.raw
  return {
    project_id: input.projectId, provider_credential_id: input.credentialId,
    name: input.name.trim() || modelId, model: modelId,
    model_type: spec?.model_type ?? input.modelType ?? (sameIdentity ? input.existing?.model_type : undefined) ?? 'language',
    ...(spec ? { spec } : {}), metadata,
  }
}
