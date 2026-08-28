import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { resetAgentStreamStopState } from '@/features/playground/stream-stop-state'
import { ChatCanvas } from './ChatCanvas'

afterEach(() => resetAgentStreamStopState())

describe('ChatCanvas terminal placeholder reconciliation', () => {
  it('does not render an empty terminal Assistant placeholder after cancellation before first token', () => {
    const html = renderToStaticMarkup(
      <ChatCanvas
        messages={[
          { role: 'user', content: 'cancel before first token' },
          { role: 'assistant', content: '', activity: null },
        ]}
        isSending={false}
        onSend={vi.fn()}
        onStop={vi.fn()}
        agentName="Agent Under Test"
      />,
    )

    expect(html).toContain('cancel before first token')
    expect(html).not.toContain('Agent Under Test')
    expect(html).not.toContain('Copy response')
  })

  it('keeps an empty Assistant placeholder visible while the Run is still active', () => {
    const html = renderToStaticMarkup(
      <ChatCanvas
        messages={[
          { role: 'user', content: 'waiting' },
          { role: 'assistant', content: '', activity: { status: 'working', message: 'Working...' } },
        ]}
        isSending
        onSend={vi.fn()}
        onStop={vi.fn()}
        agentName="Agent Under Test"
      />,
    )

    expect(html).toContain('Agent Under Test')
    expect(html).toContain('Working...')
  })

  it('keeps structured Assistant output even when textual content is empty', () => {
    const html = renderToStaticMarkup(
      <ChatCanvas
        messages={[
          { role: 'user', content: 'structured' },
          { role: 'assistant', content: '', parsed_output: { ok: true } },
        ]}
        isSending={false}
        onSend={vi.fn()}
        onStop={vi.fn()}
        agentName="Agent Under Test"
      />,
    )

    expect(html).toContain('Agent Under Test')
    expect(html).toContain('ok')
  })
})
