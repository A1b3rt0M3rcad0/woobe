import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'

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
