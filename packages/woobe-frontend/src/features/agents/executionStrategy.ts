import type { AgentRelease, ExecutionStrategyDescriptor, RuntimeEnvironment } from './types'

export const DEFAULT_EXECUTION_STRATEGY = 'standard' as const

export type AgentExecutionStrategy = string
export type ExecutionStrategySelectOption = { value: string; label: string }

export function executionStrategyFromRuntimeConfig(
  runtimeConfig: Record<string, unknown>,
): AgentExecutionStrategy {
  const value = runtimeConfig.execution_strategy
  return typeof value === 'string' && value.trim()
    ? value.trim().toLowerCase()
    : DEFAULT_EXECUTION_STRATEGY
}

export function executionStrategyForEnvironment(
  environment: RuntimeEnvironment,
  draftRuntimeConfig: Record<string, unknown>,
  releases: AgentRelease[],
): AgentExecutionStrategy {
  if (environment === 'draft') {
    return executionStrategyFromRuntimeConfig(draftRuntimeConfig)
  }

  const release = releases.find((item) => item.status === environment)
  return executionStrategyFromRuntimeConfig(release?.runtime_config ?? {})
}

export function executionStrategyDescriptor(
  catalog: ExecutionStrategyDescriptor[],
  selected: AgentExecutionStrategy,
): ExecutionStrategyDescriptor | undefined {
  return catalog.find((descriptor) => descriptor.name === selected)
}

export function executionStrategySelectOptions(
  catalog: ExecutionStrategyDescriptor[],
  selected: AgentExecutionStrategy,
): ExecutionStrategySelectOption[] {
  const options = catalog.map((descriptor) => ({
    value: descriptor.name,
    label: descriptor.display_name,
  }))

  if (!options.some((option) => option.value === selected)) {
    const fallbackLabel = selected === DEFAULT_EXECUTION_STRATEGY ? 'Standard' : selected
    return [{ value: selected, label: fallbackLabel }, ...options]
  }

  return options
}

export function withExecutionStrategy(
  runtimeConfig: Record<string, unknown>,
  strategy: AgentExecutionStrategy,
): Record<string, unknown> {
  const normalized = strategy.trim().toLowerCase() || DEFAULT_EXECUTION_STRATEGY
  return {
    ...runtimeConfig,
    execution_strategy: normalized,
  }
}
