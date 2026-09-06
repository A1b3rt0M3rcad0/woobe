import type { AgentRelease, AgentReleaseActivation } from '@/features/agents/types'

function timestamp(value?: string) {
  if (!value) return 0
  const parsed = new Date(value).getTime()
  return Number.isNaN(parsed) ? 0 : parsed
}

function stableValue(value: unknown) {
  try {
    return JSON.stringify(value ?? null)
  } catch {
    return String(value ?? '')
  }
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

export function contextAssemblerLabel(runtimeConfig: unknown) {
  const runtime = recordValue(runtimeConfig)
  const selection = recordValue(runtime.context_assembler)
  const name = typeof selection.name === 'string' && selection.name.trim()
    ? selection.name.trim()
    : 'default'
  const version = typeof selection.version === 'string' && selection.version.trim()
    ? selection.version.trim()
    : 'v1'
  return `${name}:${version}`
}

export function formatReleaseDate(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date).replace(',', '')
}

export function sessionModeLabel(mode?: string) {
  if (mode === 'stateful') return 'Stateful'
  if (mode === 'stateless') return 'Stateless'
  return 'Unknown'
}

export function promotableReleases(releases: AgentRelease[]) {
  return releases
    .filter((release) => release.snapshot_kind === 'release' && release.status !== 'production')
    .sort((left, right) => timestamp(right.created_at) - timestamp(left.created_at))
}

export function newestProductionChanges(activations: AgentReleaseActivation[]) {
  return [...activations].sort(
    (left, right) => timestamp(right.created_at) - timestamp(left.created_at),
  )
}

export function activationLabel(action: AgentReleaseActivation['action']) {
  if (action === 'rollback') return 'Rollback'
  if (action === 'reactivate') return 'Reactivated'
  return 'Deployed'
}

export function activationSummary(
  activation: AgentReleaseActivation,
  release: AgentRelease | null,
) {
  if (release?.release_notes) return release.release_notes
  if (activation.action === 'rollback') return 'A previous stable Release was restored to Production.'
  if (activation.action === 'reactivate') return 'An existing Release was returned to Production.'
  if (!activation.previous_release_id) return 'The first Release was activated in Production.'
  return 'A new Release was activated in Production.'
}

export function describeReleaseChanges(
  previous: AgentRelease | null,
  current: AgentRelease | null,
) {
  if (!current) return []
  if (!previous) return ['First Production Release activated']

  const changes: string[] = []
  const previousModel = `${previous.provider ?? '—'}/${previous.model ?? '—'}`
  const currentModel = `${current.provider ?? '—'}/${current.model ?? '—'}`

  if (previousModel !== currentModel) {
    changes.push(`Model changed from ${previousModel} to ${currentModel}`)
  }
  if (previous.session_mode !== current.session_mode) {
    changes.push(
      `Session Mode changed from ${sessionModeLabel(previous.session_mode)} to ${sessionModeLabel(current.session_mode)}`,
    )
  }
  if (previous.system_prompt !== current.system_prompt) {
    changes.push('Agent instructions were updated')
  }
  if (previous.knowledge_version_id !== current.knowledge_version_id
    || stableValue(previous.collection_ids) !== stableValue(current.collection_ids)) {
    changes.push('Knowledge binding was updated')
  }
  if (stableValue(previous.output_schema ?? previous.response_format)
    !== stableValue(current.output_schema ?? current.response_format)) {
    changes.push('Output contract was updated')
  }
  if (previous.temperature !== current.temperature
    || previous.max_output_tokens !== current.max_output_tokens) {
    changes.push('Generation settings were updated')
  }
  if (`${previous.fallback_provider ?? ''}/${previous.fallback_model ?? ''}`
    !== `${current.fallback_provider ?? ''}/${current.fallback_model ?? ''}`) {
    changes.push('Fallback model configuration was updated')
  }
  if (stableValue(previous.runtime_config) !== stableValue(current.runtime_config)) {
    changes.push('Runtime configuration was updated')
  }

  return changes.length ? changes : ['Release was reactivated without configuration changes']
}