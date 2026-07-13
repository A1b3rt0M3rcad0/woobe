import type { SourceInfo, ToolCallInfo, UsageInfo } from '@/features/playground/types'

import type { AgentNodeId, ChatTarget, Environment, NetworkBinding, NodeId } from './networkWorkspaceTypes'

export type AgentInvocationStatus = 'pending' | 'running' | 'success' | 'error' | 'skipped'

export interface NetworkAgentInvocation {
  spanId: string
  parentSpanId: string | null
  sequence: number
  nodeId?: AgentNodeId
  agentId: string
  agentName: string
  provider?: string | null
  model?: string | null
  source: NetworkBinding['source']
  version: string
  status: AgentInvocationStatus
  durationMs?: number | null
  usage?: UsageInfo | null
  costUsd?: number | null
  output?: string | null
  parsedOutput?: Record<string, unknown> | null
  outputParseError?: string | null
  tools: ToolCallInfo[]
  sources: SourceInfo[]
  children: NetworkAgentInvocation[]
}

export interface NetworkExecution {
  id: string
  traceId: string
  status: 'running' | 'success' | 'error'
  environment: Environment
  startedAt: string
  durationMs: number
  costUsd: number
  path: NodeId[]
  root: NetworkAgentInvocation
}

export interface NetworkTurn {
  id: string
  user: string
  answer: string
  parsedOutput?: Record<string, unknown> | null
  outputParseError?: string | null
  provider: string
  model: string
  usage: UsageInfo
  execution: NetworkExecution
}

export function networkLabel(target: ChatTarget) {
  if (target === 'draft') return 'Draft Revision 29'
  if (target === 'staging') return 'Staging v0.12.20260713.00'
  if (target === 'production') return 'Production v0.10.20260710.00'
  return 'Historical Release v0.8.20260701.00'
}

export function environmentForTarget(target: ChatTarget): Environment {
  return target === 'history' ? 'production' : target
}

export function currentSignature(target: ChatTarget, bindings: Record<AgentNodeId, NetworkBinding>) {
  return `${target}|${(['coordinator', 'billing', 'technical'] as AgentNodeId[])
    .map((nodeId) => {
      const binding = bindings[nodeId]
      return `${nodeId}:${binding.ref}:${binding.dirty ? 'preview' : 'saved'}`
    })
    .join('|')}`
}

export function invocationCount(root: NetworkAgentInvocation): number {
  return 1 + root.children.reduce((total, child) => total + invocationCount(child), 0)
}

export function toolCount(root: NetworkAgentInvocation): number {
  return root.tools.length + root.children.reduce((total, child) => total + toolCount(child), 0)
}

export function sourceCount(root: NetworkAgentInvocation): number {
  return root.sources.length + root.children.reduce((total, child) => total + sourceCount(child), 0)
}

export function invocationPath(root: NetworkAgentInvocation): string[] {
  const primaryChild = root.children[0]
  if (!primaryChild) return [root.agentName]
  return [root.agentName, ...invocationPath(primaryChild)]
}

function bindingFor(
  bindings: Record<AgentNodeId, NetworkBinding>,
  preferred: AgentNodeId,
): NetworkBinding {
  return bindings[preferred] ?? Object.values(bindings)[0]
}

function makeTool(name: string, input: unknown, output: unknown, durationMs: number): ToolCallInfo {
  return {
    tool_call_id: `${name}-${Math.random().toString(36).slice(2, 8)}`,
    tool_name: name,
    input,
    output,
    duration_ms: durationMs,
    status: 'completed',
    success: true,
  }
}

export function makeExecution(
  rawMessage: string,
  target: ChatTarget,
  bindings: Record<AgentNodeId, NetworkBinding>,
): { answer: string; parsedOutput?: Record<string, unknown>; execution: NetworkExecution; provider: string; model: string; usage: UsageInfo } {
  const message = rawMessage.toLowerCase()
  const technical = /api|timeout|error|incident|password|technical|status/.test(message)
  const requestJson = /json|structured|schema/.test(message)
  const coordinator = bindingFor(bindings, 'coordinator')
  const specialist = technical ? bindingFor(bindings, 'technical') : bindingFor(bindings, 'billing')
  const tertiary = technical && /invoice|billing|subscription/.test(message)
    ? bindingFor(bindings, 'billing')
    : null

  const specialistSources: SourceInfo[] = technical
    ? [
        {
          document_id: 'doc-runbook',
          chunk_id: 'chunk-api-timeout',
          document_title: 'API Incident Runbook',
          page_number: 8,
          score: 0.918,
          content_preview: 'Confirm upstream availability, inspect recent deployments and compare timeout distribution by region.',
        },
      ]
    : [
        {
          document_id: 'doc-invoice-policy',
          chunk_id: 'chunk-duplicate-charge',
          document_title: 'Invoice and Refund Policy',
          page_number: 14,
          score: 0.892,
          content_preview: 'Duplicate charges should be matched by invoice identifier and payment authorization before refund review.',
        },
        {
          document_id: 'doc-refund-procedure',
          chunk_id: 'chunk-refund-workflow',
          document_title: 'Refund Procedures',
          page_number: 7,
          score: 0.846,
          content_preview: 'Validated duplicate transactions can be escalated to the refund workflow with the original authorization reference.',
        },
      ]

  const specialistTools = technical
    ? [makeTool('check_service_status', { service: 'public-api', window: '30m' }, { status: 'degraded', region: 'sa-east-1', incidents: 1 }, 412)]
    : [makeTool('find_invoice', { query: 'duplicate charge', include_payments: true }, { invoice_id: 'inv_1042', duplicate_payment: true, refund_eligible: true }, 384)]

  const tertiaryInvocation: NetworkAgentInvocation | null = tertiary
    ? {
        spanId: 'span-billing-review',
        parentSpanId: 'span-specialist',
        sequence: 3,
        nodeId: tertiary.nodeId,
        agentId: tertiary.agent.id,
        agentName: tertiary.agent.name,
        provider: tertiary.agent.provider,
        model: tertiary.agent.model,
        source: tertiary.source,
        version: tertiary.version,
        status: 'success',
        durationMs: 438,
        usage: { input_tokens: 74, output_tokens: 18, total_tokens: 92, cost_usd: 0.002 },
        costUsd: 0.002,
        output: 'The subscription is active and the second charge is not associated with a renewal.',
        tools: [],
        sources: [],
        children: [],
      }
    : null

  const specialistInvocation: NetworkAgentInvocation = {
    spanId: 'span-specialist',
    parentSpanId: 'span-coordinator',
    sequence: 2,
    nodeId: specialist.nodeId,
    agentId: specialist.agent.id,
    agentName: specialist.agent.name,
    provider: specialist.agent.provider,
    model: specialist.agent.model,
    source: specialist.source,
    version: specialist.version,
    status: 'success',
    durationMs: technical ? 1210 : 1184,
    usage: { input_tokens: technical ? 238 : 231, output_tokens: technical ? 81 : 74, total_tokens: technical ? 319 : 305, cost_usd: technical ? 0.011 : 0.009 },
    costUsd: technical ? 0.011 : 0.009,
    output: technical
      ? 'The public API is degraded in one region. The first action is to inspect the current incident and recent deployment changes.'
      : 'The matching invoice contains a duplicated payment authorization and is eligible for refund review.',
    tools: specialistTools,
    sources: specialistSources,
    children: tertiaryInvocation ? [tertiaryInvocation] : [],
  }

  const root: NetworkAgentInvocation = {
    spanId: 'span-coordinator',
    parentSpanId: null,
    sequence: 1,
    nodeId: coordinator.nodeId,
    agentId: coordinator.agent.id,
    agentName: coordinator.agent.name,
    provider: coordinator.agent.provider,
    model: coordinator.agent.model,
    source: coordinator.source,
    version: coordinator.version,
    status: 'success',
    durationMs: 312,
    usage: { input_tokens: 84, output_tokens: 22, total_tokens: 106, cost_usd: 0.003 },
    costUsd: 0.003,
    output: technical
      ? `Classified the request as technical support and called ${specialist.agent.name}.`
      : `Classified the request as billing support and called ${specialist.agent.name}.`,
    tools: [],
    sources: [],
    children: [specialistInvocation],
  }

  const parsedOutput = requestJson
    ? {
        status: technical ? 'degraded' : 'resolved',
        routed_to: specialist.agent.name,
        action: technical ? 'inspect_incident' : 'refund_review',
        confidence: 0.96,
      }
    : undefined

  const answer = requestJson
    ? JSON.stringify(parsedOutput, null, 2)
    : technical
      ? 'Technical Support identified a degraded API region and prepared the first diagnostic steps. Review the active incident and compare it with recent deployments.'
      : 'Billing Specialist found the duplicated payment and prepared the invoice for refund review.'

  const durationMs = 1840 + (tertiaryInvocation ? 438 : 0)
  const costUsd = 0.012 + (tertiaryInvocation ? 0.002 : 0)
  const path = tertiaryInvocation?.nodeId
    ? ['entry', 'coordinator', specialist.nodeId, tertiaryInvocation.nodeId, 'end'] as NodeId[]
    : ['entry', 'coordinator', specialist.nodeId, 'end'] as NodeId[]

  return {
    answer,
    parsedOutput,
    provider: specialist.agent.provider || 'custom',
    model: specialist.agent.model || 'model',
    usage: {
      input_tokens: 84 + (specialistInvocation.usage?.input_tokens ?? 0) + (tertiaryInvocation?.usage?.input_tokens ?? 0),
      output_tokens: 22 + (specialistInvocation.usage?.output_tokens ?? 0) + (tertiaryInvocation?.usage?.output_tokens ?? 0),
      total_tokens: 106 + (specialistInvocation.usage?.total_tokens ?? 0) + (tertiaryInvocation?.usage?.total_tokens ?? 0),
      cost_usd: costUsd,
    },
    execution: {
      id: `network-execution-${Date.now()}`,
      traceId: globalThis.crypto?.randomUUID?.() ?? `trace-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
      status: 'success',
      environment: environmentForTarget(target),
      startedAt: new Date().toISOString(),
      durationMs,
      costUsd,
      path,
      root,
    },
  }
}
