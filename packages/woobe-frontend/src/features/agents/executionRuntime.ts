export const DEFAULT_INTERMEDIATE_MESSAGES_ENABLED = false

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

export function intermediateMessagesEnabledFromRuntimeConfig(
  runtimeConfig: Record<string, unknown>,
): boolean {
  const execution = record(runtimeConfig.execution)
  return typeof execution.intermediate_messages === 'boolean'
    ? execution.intermediate_messages
    : DEFAULT_INTERMEDIATE_MESSAGES_ENABLED
}

export function withIntermediateMessagesEnabled(
  runtimeConfig: Record<string, unknown>,
  enabled: boolean,
): Record<string, unknown> {
  const execution = record(runtimeConfig.execution)
  return {
    ...runtimeConfig,
    execution: {
      ...execution,
      intermediate_messages: enabled,
    },
  }
}
