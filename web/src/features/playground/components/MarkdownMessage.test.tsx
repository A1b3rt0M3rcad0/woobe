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

  it('renders horizontal rules instead of showing raw separators', () => {
    const html = renderToStaticMarkup(<MarkdownMessage content={'Intro\n\n---\n\nResumo'} />)

    expect(html).toContain('<hr')
    expect(html).toContain('Intro')
    expect(html).toContain('Resumo')
    expect(html).not.toContain('&lt;hr')
  })

  it('renders markdown tables with inline code inside cells', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage
        content={[
          '| Ferramenta | O que faz |',
          '|---|---|',
          '| `read_wiki_structure` | Mostra os tópicos disponíveis |',
          '| `ask_question` | Responde perguntas baseadas na documentação |',
        ].join('\n')}
      />,
    )

    expect(html).toContain('<table')
    expect(html).toContain('<thead')
    expect(html).toContain('<tbody')
    expect(html).toContain('Ferramenta')
    expect(html).toContain('read_wiki_structure')
    expect(html).toContain('<code')
    expect(html).not.toContain('|---|---|')
  })

  it('keeps markdown-looking tables inside code fences as code', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage
        content={[
          '```md',
          '| Ferramenta | O que faz |',
          '|---|---|',
          '| x | y |',
          '```',
        ].join('\n')}
      />,
    )

    expect(html).toContain('<pre')
    expect(html).toContain('| Ferramenta | O que faz |')
    expect(html).not.toContain('<table')
  })

  it('escapes raw html instead of injecting it', () => {
    const html = renderToStaticMarkup(<MarkdownMessage content={'<script>alert(1)</script>'} />)

    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).not.toContain('<script>alert(1)</script>')
  })
})
