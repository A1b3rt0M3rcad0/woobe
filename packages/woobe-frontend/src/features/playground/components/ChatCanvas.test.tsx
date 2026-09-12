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

describe('ChatCanvas shared Agent and Network surface', () => {
  it('uses the standalone layout for a Network empty state while preserving the Network icon', () => {
    const html = renderToStaticMarkup(
      <ChatCanvas
        entries={[]}
        isSending={false}
        onSend={vi.fn()}
        onStop={vi.fn()}
        assistantIcon="network"
        emptyTitle="Test your Network"
        emptyDescription="Execute the current Network composition."
        suggestions={['Test the Network composition.']}
        enableFirstRunSuccess={false}
      />,
    )

    expect(html).toContain('Test your Network')
    expect(html).toContain('Execute the current Network composition.')
    expect(html).toContain('Test the Network composition.')
    expect(html).toContain('lucide-workflow')
    expect(html).toContain('Attach')
    expect(html).toContain('Tools')
    expect(html).toContain('Enter to send')
  })

  it('renders Network messages with the same compact message geometry as standalone Chat', () => {
    const html = renderToStaticMarkup(
      <ChatCanvas
        entries={[
          {
            key: 'network-answer',
            message: { role: 'assistant', content: 'Network answer' },
            assistantIcon: 'network',
          },
        ]}
        isSending={false}
        onSend={vi.fn()}
        onStop={vi.fn()}
        assistantIcon="network"
        enableFirstRunSuccess={false}
      />,
    )

    expect(html).toContain('Network answer')
    expect(html).toContain('lucide-workflow')
    expect(html).toContain('rounded-container px-ui-md py-ui-sm text-product-body')
    expect(html).not.toContain('rounded-xl rounded-bl-md')
    expect(html).not.toContain('rounded-lg rounded-bl-sm')
  })
})
