import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { NetworkChatHeader } from './NetworkChatHeader'

describe('NetworkChatHeader', () => {
  it('does not render Session selector, New conversation button, or permanent Session info banners', () => {
    const html = renderToStaticMarkup(
      <NetworkChatHeader
        environment="draft"
        counts={{ draft: 2, staging: 0, release: 1 }}
        activeSessionId={null}
        versionLabel="18"
        changed={false}
        onNew={vi.fn()}
        onResetContext={vi.fn()}
      />,
    )

    expect(html).toContain('Network Chat')
    expect(html).not.toContain('New conversation. A Network Session will be created automatically when you send the first message.')
    expect(html).not.toContain('Draft sessions can include Agent Draft contexts. Runtime Keys cannot execute this mutable composition.')
    expect(html).not.toContain('New Network conversation')
    expect(html).not.toContain('Network Sessions')
    expect(html).toContain('Reset context')
  })

  it('preserves the actionable warning for an immutable Session on an earlier snapshot', () => {
    const html = renderToStaticMarkup(
      <NetworkChatHeader
        environment="production"
        counts={{ draft: 0, staging: 0, release: 2 }}
        activeSessionId="session-1"
        versionLabel="v4"
        changed
        onNew={vi.fn()}
        onResetContext={vi.fn()}
      />,
    )

    expect(html).toContain('This session belongs to an earlier production snapshot')
    expect(html).toContain('Start current snapshot conversation')
  })
})
