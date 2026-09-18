import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { ChatComposer } from './ChatComposer'

describe('ChatComposer runtime state', () => {
  it('renders the normal Stop control while an Agent Run is generating', () => {
    const html = renderToStaticMarkup(
      <ChatComposer isSending isStopping={false} onSend={vi.fn()} onStop={vi.fn()} />,
    )

    expect(html).toContain('Generating...')
    expect(html).toContain('aria-label="Stop generation"')
    expect(html).not.toContain('Stopping...')
  })

  it('renders a disabled Stopping control after cancellation is requested', () => {
    const html = renderToStaticMarkup(
      <ChatComposer isSending isStopping onSend={vi.fn()} onStop={vi.fn()} />,
    )

    expect(html).toContain('Stopping...')
    expect(html).toContain('aria-label="Stopping generation"')
    expect(html).toContain('disabled=""')
    expect(html).not.toContain('Generating...')
  })

  it('returns to the Send state after the Run reaches a terminal state', () => {
    const html = renderToStaticMarkup(
      <ChatComposer isSending={false} isStopping={false} onSend={vi.fn()} onStop={vi.fn()} />,
    )

    expect(html).toContain('Enter to send · Shift+Enter for new line')
    expect(html).not.toContain('aria-label="Stop generation"')
    expect(html).not.toContain('aria-label="Stopping generation"')
  })

  it('surfaces Run-scoped External Context beside the message composer', () => {
    const html = renderToStaticMarkup(
      <ChatComposer
        isSending={false}
        onSend={vi.fn()}
        onStop={vi.fn()}
        runContextContract={{
          current_page: {
            schema: { type: 'string' },
            required: true,
            scope: 'run',
            model: { expose: true },
          },
        }}
        runContextValues={{}}
        onRunContextValuesChange={vi.fn()}
      />,
    )

    expect(html).toContain('Run Context')
    expect(html).toContain('1 required missing')
  })

  it('keeps runtime blocking more authoritative than transient run state text', () => {
    const html = renderToStaticMarkup(
      <ChatComposer
        isSending
        isStopping
        onSend={vi.fn()}
        onStop={vi.fn()}
        runtimeBlocked
        runtimeBlockReason="Runtime disabled"
      />,
    )

    expect(html).toContain('Runtime disabled')
    expect(html).not.toContain('Stopping...')
  })
})