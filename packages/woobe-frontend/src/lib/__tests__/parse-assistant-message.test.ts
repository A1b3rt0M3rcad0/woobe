import { describe, it, expect } from 'vitest'
import { parseAssistantMessageContent } from '../parse-assistant-message'

describe('parseAssistantMessageContent', () => {
  it('pure JSON object — isPureJson: true', () => {
    const input = '{"message": "ok", "confidence": 0.92}'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(true)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('json')
    if (result.segments[0].type === 'json') {
      expect(result.segments[0].value).toEqual({ message: 'ok', confidence: 0.92 })
    }
  })

  it('pure JSON array — isPureJson: true', () => {
    const input = '[1, 2, 3]'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(true)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('json')
    if (result.segments[0].type === 'json') {
      expect(result.segments[0].value).toEqual([1, 2, 3])
    }
  })

  it('pure nested JSON — isPureJson: true', () => {
    const input = '{"a": {"b": [1, 2, {"c": 3}]}}'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(true)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('json')
    if (result.segments[0].type === 'json') {
      expect(result.segments[0].value).toEqual({ a: { b: [1, 2, { c: 3 }] } })
    }
  })

  it('text before JSON — mixed segments', () => {
    const input = 'Here is the result:\n\n{"message": "ok"}'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(2)
    expect(result.segments[0].type).toBe('text')
    expect(result.segments[1].type).toBe('json')
    if (result.segments[0].type === 'text') {
      expect(result.segments[0].content).toBe('Here is the result:\n\n')
    }
    if (result.segments[1].type === 'json') {
      expect(result.segments[1].value).toEqual({ message: 'ok' })
    }
  })

  it('text after JSON — mixed segments', () => {
    const input = '{"message": "ok"}\n\nFollow up text.'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(2)
    expect(result.segments[0].type).toBe('json')
    expect(result.segments[1].type).toBe('text')
    if (result.segments[1].type === 'text') {
      expect(result.segments[1].content).toBe('\n\nFollow up text.')
    }
  })

  it('JSON between text — three segments', () => {
    const input = 'Start.\n\n{"a": 1}\n\nEnd.'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(3)
    expect(result.segments[0].type).toBe('text')
    expect(result.segments[1].type).toBe('json')
    expect(result.segments[2].type).toBe('text')
    if (result.segments[0].type === 'text') {
      expect(result.segments[0].content).toBe('Start.\n\n')
    }
    if (result.segments[2].type === 'text') {
      expect(result.segments[2].content).toBe('\n\nEnd.')
    }
  })

  it('multiple JSON blocks — multiple json segments', () => {
    const input = 'A {"x": 1} B {"y": 2} C'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(5)
    expect(result.segments[0].type).toBe('text')
    expect(result.segments[1].type).toBe('json')
    expect(result.segments[2].type).toBe('text')
    expect(result.segments[3].type).toBe('json')
    expect(result.segments[4].type).toBe('text')
    if (result.segments[0].type === 'text') expect(result.segments[0].content).toBe('A ')
    if (result.segments[2].type === 'text') expect(result.segments[2].content).toBe(' B ')
    if (result.segments[4].type === 'text') expect(result.segments[4].content).toBe(' C')
  })

  it('plain text — no JSON detected, single text segment', () => {
    const input = 'No structured output available.'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
    if (result.segments[0].type === 'text') {
      expect(result.segments[0].content).toBe(input)
    }
  })

  it('text with non-JSON braces — treated as text', () => {
    const input = 'The value is {not json} here.'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
    if (result.segments[0].type === 'text') {
      expect(result.segments[0].content).toBe(input)
    }
  })

  it('text with template literal braces — treated as text', () => {
    const input = 'Hello ${name} and ${age}'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('invalid JSON between braces — treated as text', () => {
    const input = 'Data: {invalid: unquoted}'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('empty string — single text segment', () => {
    const result = parseAssistantMessageContent('')

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('whitespace-only string — single text segment', () => {
    const result = parseAssistantMessageContent('   \n  ')

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('JSON string containing brace characters — parsed correctly', () => {
    const input = '{"a": "text with {braces} inside"}'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(true)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('json')
    if (result.segments[0].type === 'json') {
      expect(result.segments[0].value).toEqual({ a: 'text with {braces} inside' })
    }
  })

  it('valid JSON after text with braces — only valid JSON is detected', () => {
    const input = 'Say {hello} then {"real": "json"}'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(2)
    expect(result.segments[0].type).toBe('text')
    expect(result.segments[1].type).toBe('json')
    if (result.segments[1].type === 'json') {
      expect(result.segments[1].value).toEqual({ real: 'json' })
    }
  })

  it('unmatched opening brace — everything treated as text', () => {
    const input = 'Some text { unmatched'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('JSON with trailing text after unmatched brace — partial valid JSON found', () => {
    const input = '{"a": 1} more {unmatched'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(2)
    expect(result.segments[0].type).toBe('json')
    expect(result.segments[1].type).toBe('text')
    if (result.segments[1].type === 'text') {
      expect(result.segments[1].content).toBe(' more {unmatched')
    }
  })

  it('preserves raw JSON string in segment', () => {
    const input = '{"msg": "hello"}'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(true)
    expect(result.segments[0].type).toBe('json')
    if (result.segments[0].type === 'json') {
      expect(result.segments[0].raw).toBe(input)
    }
  })

  it('does not choke on very long text with no JSON', () => {
    const input = 'a'.repeat(10000)
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('pure JSON string — isPureJson: false (only object/array get card)', () => {
    const input = '"hello world"'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('pure JSON number — isPureJson: false', () => {
    const input = '42'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('pure JSON boolean — isPureJson: false', () => {
    const input = 'true'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('JSON with escaped quotes inside strings', () => {
    const input = '{"quote": "He said \\"hello\\""}'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(true)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('json')
    if (result.segments[0].type === 'json') {
      expect(result.segments[0].value).toEqual({ quote: 'He said "hello"' })
    }
  })

  it('JavaScript code with braces — not treated as JSON', () => {
    const input = 'function test() { return true }'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('text with template interpolation braces — not treated as JSON', () => {
    const input = 'Use {id} for interpolation in the URL'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('multiple template braces like {foo} {bar} — not treated as JSON', () => {
    const input = 'Values: {foo} and {bar}'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('text with SQL like SELECT {columns} FROM {table} — not treated as JSON', () => {
    const input = 'SELECT {columns} FROM {table} WHERE id = {id}'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(false)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('text')
  })

  it('JSON with array at root — isPureJson: true', () => {
    const input = '[{"name": "Alice"}, {"name": "Bob"}]'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(true)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('json')
    if (result.segments[0].type === 'json') {
      expect(result.segments[0].value).toEqual([{ name: 'Alice' }, { name: 'Bob' }])
    }
  })

  it('nested JSON with brackets inside strings', () => {
    const input = '{"nested": {"deep": [1, {"key": "value [with] brackets"}]}}'
    const result = parseAssistantMessageContent(input)

    expect(result.isPureJson).toBe(true)
    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].type).toBe('json')
    if (result.segments[0].type === 'json') {
      const v = result.segments[0].value as Record<string, unknown>
      const nested = v.nested as Record<string, unknown>
      const deep = nested.deep as unknown[]
      expect(deep[1]).toEqual({ key: 'value [with] brackets' })
    }
  })
})
