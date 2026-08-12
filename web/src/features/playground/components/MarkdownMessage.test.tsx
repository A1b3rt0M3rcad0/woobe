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

  it('renders inline code as subdued code instead of a primary badge', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage content={'Use `repoName` no formato `proprietario/repositorio`.'} />,
    )

    expect(html).toContain('repoName')
    expect(html).toContain('proprietario/repositorio')
    expect(html).toContain('bg-white/[0.06]')
    expect(html).toContain('border-white/10')
    expect(html).not.toContain('bg-primary/10')
    expect(html).not.toContain('border-primary/20')
  })

  it('renders inline code nested inside bold markdown without leaking backticks', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage content={'1. **`explicacao`** → Fala o que a ferramenta faz.'} />,
    )

    expect(html).toContain('<strong')
    expect(html).toContain('<code')
    expect(html).toContain('explicacao')
    expect(html).not.toContain('`explicacao`')
  })

  it('renders mixed bold text with nested inline code', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage content={'**Campo `repoName` obrigatório**'} />,
    )

    expect(html).toContain('<strong')
    expect(html).toContain('<code')
    expect(html).toContain('Campo')
    expect(html).toContain('repoName')
    expect(html).toContain('obrigatório')
    expect(html).not.toContain('`repoName`')
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
    expect(html).toContain('bg-surface/70')
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

  it('renders the calculus response format as inline MathML', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage
        content={[
          'Derivada de x² + x:',
          'Resultado: \\(2x + 1\\)',
          '',
          'Integral de x² + x:',
          'Resultado: \\(\\frac{1}{3}x^3 + \\frac{1}{2}x^2\\)',
          '',
          'Simplificação de x² + x:',
          'Resultado: \\(x^2 + x\\)',
        ].join('\n')}
      />,
    )

    expect(html).toContain('data-math-inline="true"')
    expect(html).toContain('<math')
    expect(html).toContain('<mfrac')
    expect(html).toContain('<msup')
    expect(html).not.toContain('\\(')
  })

  it('keeps currency values with dollar signs as plain text', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage content={'O plano custa $10 e o limite é $20 por mês.'} />,
    )

    expect(html).toContain('$10')
    expect(html).toContain('$20')
    expect(html).not.toContain('data-math-inline')
  })

  it('renders display math with sums, indices and fractions', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage
        content={[
          'Soma dos primeiros termos:',
          '',
          '\\[',
          '\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}',
          '\\]',
        ].join('\n')}
      />,
    )

    expect(html).toContain('data-math-display="true"')
    expect(html).toContain('<msubsup')
    expect(html).toContain('<mfrac')
  })

  it('renders math inside markdown table cells', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage
        content={[
          '| Operação | Resultado |',
          '|---|---|',
          '| Derivada | \\(2x + 1\\) |',
          '| Integral | \\(\\frac{x^3}{3}\\) |',
        ].join('\n')}
      />,
    )

    expect(html).toContain('<table')
    expect(html).toContain('data-math-inline="true"')
    expect(html).toContain('<mfrac')
  })

  it('keeps mathematical delimiters inside code fences as literal code', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage
        content={[
          '```txt',
          '\\(x^2 + y^2\\)',
          '\\frac{1}{2}',
          '```',
        ].join('\n')}
      />,
    )

    expect(html).toContain('<pre')
    expect(html).toContain('\\(x^2 + y^2\\)')
    expect(html).toContain('\\frac{1}{2}')
    expect(html).not.toContain('data-math-inline')
    expect(html).not.toContain('data-math-display')
  })

  it('escapes raw html instead of injecting it', () => {
    const html = renderToStaticMarkup(<MarkdownMessage content={'<script>alert(1)</script>'} />)

    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).not.toContain('<script>alert(1)</script>')
  })
})
