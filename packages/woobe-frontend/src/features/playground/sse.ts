export interface SseFrame {
  event: string | null
  id: string | null
  data: string
}

function parseFrame(raw: string): SseFrame | null {
  let event: string | null = null
  let id: string | null = null
  const data: string[] = []

  for (const line of raw.split(/\r?\n/)) {
    if (!line || line.startsWith(':')) continue
    const separator = line.indexOf(':')
    const field = separator >= 0 ? line.slice(0, separator) : line
    let value = separator >= 0 ? line.slice(separator + 1) : ''
    if (value.startsWith(' ')) value = value.slice(1)

    if (field === 'event') event = value
    if (field === 'id') id = value
    if (field === 'data') data.push(value)
  }

  if (data.length === 0) return null
  return { event, id, data: data.join('\n') }
}

export class SseFrameParser {
  private buffer = ''

  push(chunk: string): SseFrame[] {
    this.buffer += chunk
    const frames: SseFrame[] = []

    while (true) {
      const match = /\r?\n\r?\n/.exec(this.buffer)
      if (!match || match.index == null) break
      const raw = this.buffer.slice(0, match.index)
      this.buffer = this.buffer.slice(match.index + match[0].length)
      const frame = parseFrame(raw)
      if (frame) frames.push(frame)
    }

    return frames
  }

  finish(finalChunk = ''): SseFrame[] {
    const frames = this.push(finalChunk)
    const remaining = this.buffer.trim()
    this.buffer = ''
    if (remaining) {
      const frame = parseFrame(remaining)
      if (frame) frames.push(frame)
    }
    return frames
  }
}

export function parseSseJson(frame: SseFrame): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(frame.data)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : null
  } catch {
    return null
  }
}
