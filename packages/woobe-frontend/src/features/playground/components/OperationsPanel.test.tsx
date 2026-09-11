import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./AgentRunOperationalView', () => ({
  AgentRunOperationalView: ({ runId, traceId }: { runId?: string | null; traceId?: string | null }) => (
    <div data-run-id={runId ?? ''} data-trace-id={traceId ?? ''}>Agent Run</div>
  ),
}))
vi.mock('./AgentRunEvidencePanel', () => ({
  AgentRunEvidencePanel: ({ runId, traceId }: { runId?: string | null; traceId?: string | null }) => (
    <div data-evidence-run-id={runId ?? ''} data-evidence-trace-id={traceId ?? ''}>Evidence</div>
  ),
}))

import { resetAgentStreamStopState, setAgentStreamStopState } from '@/features/playground/stream-stop-state'
import { OperationsPanel } from './OperationsPanel'

const baseProps = {
  activeTab: 'sessions' as const,
  lastResponse: null,
  lastRequestPayload: null,
  rawEvents: [],
  traces: [],
  selectedTraceId: null,
  sessions: [],
  sessionId: null,
  onSelectTrace: vi.fn(),
  onSelectSession: vi.fn(),
}

afterEach(() => resetAgentStreamStopState())

describe('OperationsPanel Session lifecycle guard', () => {
  it('blocks Session interactions while an Agent Run is active', () => {
    setAgentStreamStopState('running')

    const html = renderToStaticMarkup(<OperationsPanel {...baseProps} />)

    expect(html).toContain('An Agent Run is active')
    expect(html).toContain('pointer-events-none')
  })

  it('keeps Session interactions blocked while cancellation is finalizing', () => {
    setAgentStreamStopState('stopping')

    const html = renderToStaticMarkup(<OperationsPanel {...baseProps} />)

    expect(html).toContain('Stopping the active Agent Run')
    expect(html).toContain('pointer-events-none')
  })

  it('does not apply the lifecycle guard after the Run becomes terminal', () => {
    resetAgentStreamStopState()

    const html = renderToStaticMarkup(<OperationsPanel {...baseProps} />)

    expect(html).not.toContain('An Agent Run is active')
    expect(html).not.toContain('Stopping the active Agent Run')
    expect(html).not.toContain('pointer-events-none opacity-60')
  })
})

describe('OperationsPanel Agent Run identity', () => {
  it('opens Run details with the canonical Agent Run id and keeps Trace as fallback evidence', () => {
    const html = renderToStaticMarkup(
      <OperationsPanel
        {...baseProps}
        activeTab="traces"
        selectedTraceId="trace-1"
        traces={[{
          id: 'trace-1',
          run_id: 'run-1',
          title: 'Agent Run completed',
          timestamp: '2026-09-10T20:00:00Z',
          status: 'success',
          latency_ms: 100,
          model: 'model',
          provider: 'provider',
          input_tokens: 10,
          output_tokens: 5,
          total_tokens: 15,
          cost_usd: 0.001,
          trace_id: 'trace-1',
          response: null,
        }]}
      />,
    )

    expect(html).toContain('data-run-id="run-1"')
    expect(html).toContain('data-trace-id="trace-1"')
  })
})
