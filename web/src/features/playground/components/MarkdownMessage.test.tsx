import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { MarkdownMessage } from './MarkdownMessage'

describe('MarkdownMessage', () => {
  it('renders headings, lists, code fences and links', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage
        content={`# Title\n\n- item one\n- item two\n\n\`inline\`\n\n\`\`\`ts\nconst ok = true\n\`\`\`\n\nhttps://example.com`}
      />,
    )

    expect(html).toContain('<h1')
    expect(html).toContain('Title')
    expect(html).toContain('<ul')
    expect(html).toContain('item one')
    expect(html).toContain('<code')
    expect(html).toContain('const ok = true')
    expect(html).toContain('href="https://example.com"')
  })

  it('escapes raw html instead of injecting it', () => {
    const html = renderToStaticMarkup(<MarkdownMessage content={'<script>alert(1)</script>'} />)

    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).not.toContain('<script>alert(1)</script>')
  })
})
