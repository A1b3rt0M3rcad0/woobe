import type { Tool } from './types'

const EXTERNAL_CONTEXT_TEMPLATE = /\{\{\s*external_context\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g
const PROJECT_ENV_TEMPLATE = /\{\{\s*project_env\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g

export interface ToolRuntimeDependencies {
  externalContextFields: Set<string>
  projectEnvironmentKeys: Set<string>
}

export interface ToolRuntimeCompatibility {
  compatible: boolean
  missingExternalContext: string[]
  missingProjectEnvironment: string[]
  projectEnvironmentUnavailable: boolean
}

function recordValue(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function collectFromValue(value: unknown, dependencies: ToolRuntimeDependencies): void {
  if (typeof value === 'string') {
    for (const match of value.matchAll(EXTERNAL_CONTEXT_TEMPLATE)) {
      dependencies.externalContextFields.add(match[1])
    }
    for (const match of value.matchAll(PROJECT_ENV_TEMPLATE)) {
      dependencies.projectEnvironmentKeys.add(match[1])
    }
    return
  }

  if (Array.isArray(value)) {
    for (const item of value) collectFromValue(item, dependencies)
    return
  }

  const record = recordValue(value)
  if (!record) return

  const source = recordValue(record.source)
  const kind = source?.kind
  const field = typeof source?.field === 'string' ? source.field.trim() : ''
  if (kind === 'context' && field) dependencies.externalContextFields.add(field)
  if (kind === 'project_environment' && field) dependencies.projectEnvironmentKeys.add(field)

  for (const child of Object.values(record)) {
    collectFromValue(child, dependencies)
  }
}

export function collectToolRuntimeDependencies(tool: Tool): ToolRuntimeDependencies {
  const dependencies: ToolRuntimeDependencies = {
    externalContextFields: new Set<string>(),
    projectEnvironmentKeys: new Set<string>(),
  }
  collectFromValue(tool.config || {}, dependencies)
  return dependencies
}

export function getToolRuntimeCompatibility(
  tool: Tool,
  externalContextFields: ReadonlySet<string>,
  projectEnvironmentKeys: ReadonlySet<string> | null,
): ToolRuntimeCompatibility {
  const dependencies = collectToolRuntimeDependencies(tool)
  const missingExternalContext = [...dependencies.externalContextFields]
    .filter((field) => !externalContextFields.has(field))
    .sort()
  const projectEnvironmentUnavailable = (
    projectEnvironmentKeys === null
    && dependencies.projectEnvironmentKeys.size > 0
  )
  const missingProjectEnvironment = projectEnvironmentKeys === null
    ? []
    : [...dependencies.projectEnvironmentKeys]
        .filter((key) => !projectEnvironmentKeys.has(key))
        .sort()

  return {
    compatible: (
      missingExternalContext.length === 0
      && missingProjectEnvironment.length === 0
      && !projectEnvironmentUnavailable
    ),
    missingExternalContext,
    missingProjectEnvironment,
    projectEnvironmentUnavailable,
  }
}
