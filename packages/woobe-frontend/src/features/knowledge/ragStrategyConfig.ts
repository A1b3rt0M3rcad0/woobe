export const DEFAULT_RAG_STRATEGY = 'classic'

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

export function normalizeRagStrategy(value: unknown): string {
  if (typeof value !== 'string') return DEFAULT_RAG_STRATEGY
  const normalized = value.trim().toLowerCase()
  return normalized || DEFAULT_RAG_STRATEGY
}

export function getRagStrategy(runtimeConfig: Record<string, unknown>): string {
  return normalizeRagStrategy(record(runtimeConfig.rag).strategy)
}

export function withRagStrategy(
  runtimeConfig: Record<string, unknown>,
  strategy: string,
): Record<string, unknown> {
  return {
    ...runtimeConfig,
    rag: {
      ...record(runtimeConfig.rag),
      strategy: normalizeRagStrategy(strategy),
    },
  }
}

export function mergeRagRuntimeConfig(
  runtimeConfig: Record<string, unknown>,
  ragConfig: object,
): Record<string, unknown> {
  return {
    ...runtimeConfig,
    rag: {
      ...record(runtimeConfig.rag),
      ...ragConfig,
    },
  }
}
