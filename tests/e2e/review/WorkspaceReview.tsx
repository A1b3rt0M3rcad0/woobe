import { useState } from 'react'
import { ThemeSelect } from '../../../packages/woobe-frontend/src/features/appearance/ThemeSelect'
import { ChatCanvas } from '../../../packages/woobe-frontend/src/features/playground/components/ChatCanvas'
import type { ChatMessage } from '../../../packages/woobe-frontend/src/features/playground/types'
import { NetworkRunDiagnosticsPanel } from '../../../packages/woobe-frontend/src/features/network/components/NetworkRunDiagnosticsPanel'
import { NetworkTraceInvocation } from '../../../packages/woobe-frontend/src/features/network/components/NetworkTraceTree'
import type { NetworkAgentInvocation, NetworkExecution } from '../../../packages/woobe-frontend/src/features/network/components/networkChatExecution'
import { createNetworkTraceRecord } from '../../../packages/woobe-frontend/src/features/network/components/networkObservabilityFactory'

function invocation(depth: number): NetworkAgentInvocation {
  return { spanId: `span-${depth}`, runId: `run-${depth}`, parentSpanId: depth ? `span-${depth-1}` : null, sequence: depth,
    nodeId: `node-${depth}`, agentId: `agent-${depth}`, agentName: `Customer Operations Evidence Specialist with a long name ${depth}`,
    agentSessionId: null, contextState: 'stateless', previousInvocationCount: 0, childTraceId: null,
    provider: 'custom', model: 'review-model', source: 'draft', version: 'r2', status: 'success', durationMs: 1690,
    output: `Result at depth ${depth}`, costUsd: depth === 8 ? null : .00000004, tools: [], sources: [], children: depth < 8 ? [invocation(depth + 1)] : [],
  }
}
const root = invocation(0)
const execution: NetworkExecution = { id: 'network-design', traceId: null, environment: 'draft', status: 'success', startedAt: '2026-06-20T12:00:00Z', durationMs: 2300, costUsd: null, path: [], root }
const trace = createNetworkTraceRecord({ execution, environment: 'draft', bindings: {}, networkSessionId: 'session-design', title: 'Review request', userMessage: 'Review request', answer: 'Reviewed' })
export const originalStructuredValue = { intent: 'customer_context', evidence: Array.from({ length: 30 }, (_, i) => ({ id: i, text: 'Original identifier and a long structured value '.repeat(8) })), final_answer: 'Request reviewed.' }

export function WorkspaceReview() {
  const [scenario, setScenario] = useState('initial')
  const [value, setValue] = useState('')
  const [context, setContext] = useState<Record<string, unknown>>({})
  const [stopped, setStopped] = useState(false)
  const [sent, setSent] = useState('')
  const short: ChatMessage[] = [{ role: 'user', content: 'Review this request.' }, { role: 'assistant', content: 'Request reviewed with the available evidence.' }]
  const messages: ChatMessage[] = scenario === 'initial' || scenario === 'blocked' ? [] : scenario === 'long' ? Array.from({ length: 40 }, (_, i) => ({ role: i % 2 ? 'assistant' : 'user', content: `Conversation message ${i}. ${'Readable conversation content. '.repeat(12)}` })) : scenario === 'structured' ? [{ role: 'assistant', content: JSON.stringify(originalStructuredValue), parsed_output: originalStructuredValue }] : scenario === 'error' ? [{ role: 'assistant', content: 'The provider could not complete this Run. Your conversation is preserved.' }] : short
  return <div>
    <div className="mb-ui-md flex flex-wrap gap-ui-md"><ThemeSelect /><label>Scenario <select aria-label="Scenario" value={scenario} onChange={e => { setScenario(e.target.value); setStopped(false) }} className="h-control-sm border border-control-border bg-surface px-ui-sm">{['initial','short','long','structured','running','error','blocked'].map(item => <option key={item}>{item}</option>)}</select></label><p role="status">{stopped ? 'Stop requested' : sent}</p></div>
    <div className="grid min-w-0 gap-ui-md xl:grid-cols-[22rem_minmax(0,1fr)]">
      <section aria-label="Network diagnostics" className="min-w-0 rounded-control border border-border bg-surface p-ui-md"><NetworkRunDiagnosticsPanel projectId="project-a" executionId="network-design" running={false} root={root} /></section>
      <section aria-label="Conversation review" className="flex h-[44rem] min-w-0 flex-col overflow-hidden rounded-control border border-border"><ChatCanvas messages={messages} isSending={scenario === 'running' && !stopped} runtimeBlocked={scenario === 'blocked'} runtimeBlockReason="Required model configuration is incomplete. Review the model settings." onSend={setSent} onStop={() => setStopped(true)} composerValue={value} onComposerValueChange={setValue} externalContextContract={{ customer_id: { schema: { type: 'string' }, required: true } }} externalContextValues={context} onExternalContextValuesChange={setContext} /></section>
    </div>
    <section aria-label="Deep invocation tree" className="mt-ui-md w-full max-w-sm"><NetworkTraceInvocation invocation={root} trace={trace} depth={0} onOpenAgent={() => {}} /></section>
  </div>
}
