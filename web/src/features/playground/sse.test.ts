import { describe, expect, it } from 'vitest'
import { SseFrameParser, parseSseJson } from './sse'

describe('SseFrameParser', () => {
  it('reassembles fragmented frames', () => {
    const parser = new SseFrameParser()
    expect(parser.push('data: {"type":"to')).toEqual([])
    expect(parser.push('ken","content":"hello"}\n\n')).toHaveLength(1)
  })

  it('supports multiline CRLF frames', () => {
    const parser = new SseFrameParser()
    const frames = parser.push('event: custom\r\nid: 42\r\ndata: first\r\ndata: second\r\n\r\n')
    expect(frames).toEqual([{ event: 'custom', id: '42', data: 'first\nsecond' }])
  })

  it('flushes the final buffer', () => {
    const parser = new SseFrameParser()
    parser.push('data: {"type":"done"}')
    expect(parseSseJson(parser.finish()[0])).toEqual({ type: 'done' })
  })

  it('isolates malformed JSON', () => {
    const parser = new SseFrameParser()
    const frames = parser.push('data: invalid\n\ndata: {"type":"done"}\n\n')
    expect(parseSseJson(frames[0])).toBeNull()
    expect(parseSseJson(frames[1])).toEqual({ type: 'done' })
  })
})
