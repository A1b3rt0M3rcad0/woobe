export const DEFAULT_EXECUTION_STRATEGY = 'standard' as const

export type AgentExecutionStrategy = typeof DEFAULT_EXECUTION_STRATEGY

export function executionStrategyFromRuntimeConfig(
  runtimeConfig: Record<string, unknown>,
): AgentExecutionStrategy {
  const value = runtimeConfig.execution_strategy
  return value === DEFAULT_EXECUTION_STRATEGY
    ? value
    : DEFAULT_EXECUTION_STRATEGY
}

export function withExecutionStrategy(
  runtimeConfig: Record<string, unknown>,
  strategy: AgentExecutionStrategy,
): Record<string, unknown> {
  return {
    ...runtimeConfig,
    execution_strategy: strategy,
  }
}
