export { providerModelCapabilities } from '@/features/provider-models/capabilities'

export type ContextBudgetConfig = {
  maxInputUnits: number | null
  runtimeReserveUnits: number
}

export type ContextCapacity = {
  contextWindow: number | null
  modelMaxOutputTokens: number | null
  effectiveOutputReserve: number
  modelUsableInput: number | null
  configuredInputBudget: number | null
  effectiveInputBudget: number | null
  budgetClamped: boolean
  budgetPreservationRatio: number | null
}

export function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

export function positiveIntegerOrNull(value: unknown): number | null {
  const parsed = typeof value === 'number'
    ? value
    : typeof value === 'string' && value.trim()
      ? Number(value)
      : Number.NaN
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

export function nonNegativeInteger(value: unknown, fallback = 0): number {
  const parsed = typeof value === 'number'
    ? value
    : typeof value === 'string' && value.trim()
      ? Number(value)
      : Number.NaN
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : fallback
}

export function readContextBudget(runtimeConfig: Record<string, unknown>): ContextBudgetConfig {
  const context = recordValue(runtimeConfig.context)
  const budget = recordValue(context.budget)
  return {
    maxInputUnits: positiveIntegerOrNull(budget.max_input_units),
    runtimeReserveUnits: nonNegativeInteger(budget.runtime_reserve_units),
  }
}

export function withContextBudget(
  runtimeConfig: Record<string, unknown>,
  budgetConfig: ContextBudgetConfig,
): Record<string, unknown> {
  const context = recordValue(runtimeConfig.context)
  const budget = recordValue(context.budget)
  return {
    ...runtimeConfig,
    context: {
      ...context,
      budget: {
        ...budget,
        max_input_units: budgetConfig.maxInputUnits,
        runtime_reserve_units: budgetConfig.runtimeReserveUnits,
      },
    },
  }
}

export function calculateContextCapacity({
  contextWindow,
  modelMaxOutputTokens,
  configuredOutputTokens,
  runtimeReserveUnits,
  configuredInputBudget,
}: {
  contextWindow: number | null
  modelMaxOutputTokens: number | null
  configuredOutputTokens: number
  runtimeReserveUnits: number
  configuredInputBudget: number | null
}): ContextCapacity {
  const effectiveOutputReserve = modelMaxOutputTokens != null
    ? Math.min(configuredOutputTokens, modelMaxOutputTokens)
    : configuredOutputTokens
  const modelUsableInput = contextWindow != null
    ? Math.max(0, contextWindow - effectiveOutputReserve - runtimeReserveUnits)
    : null
  const effectiveInputBudget = modelUsableInput != null && configuredInputBudget != null
    ? Math.min(modelUsableInput, configuredInputBudget)
    : modelUsableInput ?? configuredInputBudget
  const budgetClamped = configuredInputBudget != null
    && modelUsableInput != null
    && configuredInputBudget > modelUsableInput
  const budgetPreservationRatio = configuredInputBudget != null
    && configuredInputBudget > 0
    && effectiveInputBudget != null
    ? effectiveInputBudget / configuredInputBudget
    : null

  return {
    contextWindow,
    modelMaxOutputTokens,
    effectiveOutputReserve,
    modelUsableInput,
    configuredInputBudget,
    effectiveInputBudget,
    budgetClamped,
    budgetPreservationRatio,
  }
}

export function presetInputBudget(modelUsableInput: number | null, ratio: number): number | null {
  if (modelUsableInput == null || modelUsableInput <= 0) return null
  return Math.max(256, Math.floor(modelUsableInput * ratio))
}
