import { describe, expect, it } from 'vitest'

import { parseAssistantMessageContent } from './parse-assistant-message'

describe('parseAssistantMessageContent', () => {
  it('parses fenced json as a json segment without leaking markdown fences', () => {
    const input = [
      'Claro! Vou criar um JSON para você seguindo o que pediu:',
      '',
      '```json',
      '{',
      '  "message": {',
      '    "explicacao": "A ferramenta retorna a estrutura da documentação",',
      '    "json_exemplo": {',
      '      "ferramenta": "deepwiki_read_wiki_structure",',
      '      "repositorio": "facebook/react"',
      '    }',
      '  }',
      '}',
      '```',
      '',
      '**Explicação detalhada:**',
      '',
      '1. **explicacao** → Fala o que a ferramenta faz.',
      '2. **json_exemplo** → Mostra um exemplo prático.',
    ].join('\n')

    const parsed = parseAssistantMessageContent(input)

    expect(parsed.isPureJson).toBe(false)
    expect(parsed.segments).toHaveLength(3)
    expect(parsed.segments[0]).toMatchObject({ type: 'text' })
    expect(parsed.segments[1]).toMatchObject({ type: 'json' })
    expect(parsed.segments[2]).toMatchObject({ type: 'text' })

    expect(parsed.segments[0].type === 'text' ? parsed.segments[0].content : '').toContain('Claro!')
    expect(parsed.segments[0].type === 'text' ? parsed.segments[0].content : '').not.toContain('```json')
    expect(parsed.segments[2].type === 'text' ? parsed.segments[2].content : '').toContain('**Explicação detalhada:**')
    expect(parsed.segments[2].type === 'text' ? parsed.segments[2].content : '').not.toContain('```')
  })

  it('keeps non-json fenced code as markdown text', () => {
    const input = [
      'Exemplo:',
      '',
      '```ts',
      'const payload = { ok: true }',
      '```',
    ].join('\n')

    const parsed = parseAssistantMessageContent(input)

    expect(parsed.segments).toHaveLength(1)
    expect(parsed.segments[0]).toMatchObject({ type: 'text' })
    expect(parsed.segments[0].type === 'text' ? parsed.segments[0].content : '').toContain('```ts')
    expect(parsed.segments[0].type === 'text' ? parsed.segments[0].content : '').toContain('const payload')
  })

  it('keeps invalid fenced json as markdown text', () => {
    const input = [
      '```json',
      '{ invalid json }',
      '```',
    ].join('\n')

    const parsed = parseAssistantMessageContent(input)

    expect(parsed.segments).toHaveLength(1)
    expect(parsed.segments[0]).toMatchObject({ type: 'text' })
    expect(parsed.segments[0].type === 'text' ? parsed.segments[0].content : '').toContain('```json')
  })
})
