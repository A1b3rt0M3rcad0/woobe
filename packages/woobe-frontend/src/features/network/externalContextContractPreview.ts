import type { Agent, ExternalContextFieldContract } from '@/features/agents/types'
import type { NetworkDefinition } from './types'

type EffectiveField = ExternalContextFieldContract & {
  consumers?: Record<string, Record<string, unknown>>
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function fields(value: unknown): Record<string, EffectiveField> {
  const raw = record(value)
  const nested = raw.fields
  return (
    Object.prototype.hasOwnProperty.call(raw, 'fields')
    && nested
    && typeof nested === 'object'
    && !Array.isArray(nested)
      ? record(nested)
      : raw
  ) as Record<string, EffectiveField>
}

function clone<T>(value: T): T {
  if (value === undefined || value === null) return value
  return JSON.parse(JSON.stringify(value)) as T
}

function agentDraftExternalContext(agent: Agent | undefined): unknown {
  return record(agent?.settings).external_context_contract
}

function schemaEquals(left: unknown, right: unknown): boolean {
  return JSON.stringify(record(left)) === JSON.stringify(record(right))
}

function scopeOf(field: EffectiveField): 'run' | 'session' {
  return field.scope === 'session' ? 'session' : 'run'
}

export function previewNetworkDraftExternalContextContract({
  persistedEffectiveContract,
  definition,
  agents,
  liveDraftContractsByNodeId = {},
}: {
  persistedEffectiveContract: unknown
  definition: NetworkDefinition
  agents: Agent[]
  liveDraftContractsByNodeId?: Record<string, unknown>
}): Record<string, unknown> {
  const nodeIds = new Set(definition.nodes.map((node) => node.id))
  const draftNodeIds = new Set(
    definition.nodes
      .filter((node) => node.binding.source === 'draft')
      .map((node) => node.id),
  )
  const effective = clone(fields(persistedEffectiveContract))

  for (const [name, field] of Object.entries(effective)) {
    const consumers = record(field.consumers)
    const retained = Object.fromEntries(
      Object.entries(consumers).filter(([consumer]) => (
        nodeIds.has(consumer) && !draftNodeIds.has(consumer)
      )),
    )
    if (Object.keys(retained).length === 0) delete effective[name]
    else field.consumers = retained
  }

  const agentsById = new Map(agents.map((agent) => [agent.id, agent]))
  for (const node of definition.nodes) {
    if (node.binding.source !== 'draft') continue
    const contract = fields(
      Object.prototype.hasOwnProperty.call(liveDraftContractsByNodeId, node.id)
        ? liveDraftContractsByNodeId[node.id]
        : agentDraftExternalContext(agentsById.get(node.agent_id)),
    )

    for (const [name, rawField] of Object.entries(contract)) {
      const field = record(rawField) as EffectiveField
      const existing = effective[name] as EffectiveField | undefined
      const scope = scopeOf(field)

      if (
        existing
        && (
          !schemaEquals(existing.schema, field.schema)
          || scopeOf(existing) !== scope
        )
      ) {
        // The Network is currently invalid because two Agents disagree about
        // the same field. Keep the persisted compatible contribution until
        // the normal Network validation boundary reports the conflict.
        continue
      }

      const next: EffectiveField = existing ?? {
        schema: clone(record(field.schema)),
        consumers: {},
      }
      if (field.scope === 'session') next.scope = 'session'
      else delete next.scope

      const consumers = record(next.consumers)
      const consumer: Record<string, unknown> = {
        required: Boolean(field.required),
        model: {
          expose: Boolean(
            field.model
            && typeof field.model === 'object'
            && !Array.isArray(field.model)
            && (field.model as Record<string, unknown>).expose,
          ),
        },
      }
      if (Object.prototype.hasOwnProperty.call(field, 'default')) consumer.default = clone(field.default)
      if (typeof field.description === 'string') consumer.description = field.description
      consumers[node.id] = consumer
      next.consumers = consumers
      effective[name] = next
    }
  }

  return effective
}
