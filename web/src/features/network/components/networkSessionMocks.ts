import { currentSignature, networkLabel } from './networkChatExecution'
import { hashComposition } from './networkObservabilityTypes'
import type { AgentNodeId, Environment, NetworkBinding } from './networkWorkspaceTypes'
import type { NetworkAgentContext, NetworkSession, NetworkSessionsByEnvironment } from './networkSessionTypes'

function context(
  sessionId: string,
  binding: NetworkBinding,
  invocationCount: number,
  messageCount: number,
  minutesAgo: number,
): NetworkAgentContext {
  const stateless = binding.agent.session_mode === 'stateless'
  const time = new Date(Date.now() - minutesAgo * 60_000).toISOString()
  return {
    id: `context-${sessionId}-${binding.nodeId}`,
    networkSessionId: sessionId,
    nodeId: binding.nodeId,
    agentId: binding.agent.id,
    agentName: binding.agent.name,
    sessionMode: stateless ? 'stateless' : 'stateful',
    agentSessionId: stateless ? null : `agent-session-${sessionId}-${binding.nodeId}`,
    source: binding.source,
    version: binding.version,
    invocationCount,
    messageCount: stateless ? 0 : messageCount,
    createdAt: time,
    lastInvokedAt: time,
  }
}

function session({
  id,
  title,
  environment,
  bindings,
  minutesAgo,
  messageCount,
  traceCount,
  contexts,
}: {
  id: string
  title: string
  environment: Environment
  bindings: Record<AgentNodeId, NetworkBinding>
  minutesAgo: number
  messageCount: number
  traceCount: number
  contexts: Array<{ nodeId: AgentNodeId; invocations: number; messages: number }>
}): NetworkSession {
  const lastMessageAt = new Date(Date.now() - minutesAgo * 60_000).toISOString()
  return {
    id,
    projectId: bindings.coordinator.agent.project_id,
    networkId: `network-${bindings.coordinator.agent.project_id}`,
    title,
    environment,
    networkVersion: networkLabel(environment),
    compositionHash: hashComposition(currentSignature(environment, bindings)),
    status: 'active',
    createdAt: new Date(Date.now() - (minutesAgo + 120) * 60_000).toISOString(),
    lastMessageAt,
    messageCount,
    traceCount,
    agentContexts: contexts.map((item) => context(id, bindings[item.nodeId], item.invocations, item.messages, minutesAgo)),
  }
}

export function createMockNetworkSessions({
  draft,
  staging,
  production,
}: {
  draft: Record<AgentNodeId, NetworkBinding>
  staging: Record<AgentNodeId, NetworkBinding>
  production: Record<AgentNodeId, NetworkBinding>
}): NetworkSessionsByEnvironment {
  return {
    draft: [
      session({
        id: 'network-session-draft-current',
        title: 'API timeout diagnosis',
        environment: 'draft',
        bindings: draft,
        minutesAgo: 21,
        messageCount: 4,
        traceCount: 2,
        contexts: [
          { nodeId: 'coordinator', invocations: 2, messages: 4 },
          { nodeId: 'technical', invocations: 2, messages: 4 },
        ],
      }),
      session({
        id: 'network-session-draft-previous',
        title: 'Subscription routing review',
        environment: 'draft',
        bindings: draft,
        minutesAgo: 180,
        messageCount: 6,
        traceCount: 3,
        contexts: [
          { nodeId: 'coordinator', invocations: 3, messages: 6 },
          { nodeId: 'billing', invocations: 2, messages: 4 },
        ],
      }),
    ],
    staging: [
      session({
        id: 'network-session-staging-current',
        title: 'Password reset validation',
        environment: 'staging',
        bindings: staging,
        minutesAgo: 68,
        messageCount: 2,
        traceCount: 1,
        contexts: [
          { nodeId: 'coordinator', invocations: 1, messages: 2 },
          { nodeId: 'technical', invocations: 1, messages: 2 },
        ],
      }),
    ],
    production: [
      session({
        id: 'network-session-production-current',
        title: 'Duplicate invoice investigation',
        environment: 'production',
        bindings: production,
        minutesAgo: 7,
        messageCount: 4,
        traceCount: 2,
        contexts: [
          { nodeId: 'coordinator', invocations: 2, messages: 4 },
          { nodeId: 'billing', invocations: 2, messages: 4 },
        ],
      }),
    ],
  }
}
