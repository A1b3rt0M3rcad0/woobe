export type AssistantMessageSegment =
  | { type: 'text'; content: string }
  | { type: 'json'; value: unknown; raw: string }

export interface ParsedAssistantMessage {
  isPureJson: boolean
  segments: AssistantMessageSegment[]
}

type JsonParseResult =
  | { ok: true; value: unknown }
  | { ok: false }

type FenceBlock = {
  start: number
  end: number
  language: string
  content: string
  closed: boolean
}

function parseJson(raw: string): JsonParseResult {
  try {
    return { ok: true, value: JSON.parse(raw) }
  } catch {
    return { ok: false }
  }
}

function isJsonLanguage(language: string): boolean {
  const normalized = language.trim().toLowerCase()
  return normalized === 'json' || normalized === 'jsonc' || normalized === 'application/json'
}

function lineAt(source: string, start: number): { text: string; end: number; next: number } {
  const newline = source.indexOf('\n', start)
  if (newline === -1) {
    return { text: source.slice(start), end: source.length, next: source.length }
  }
  return { text: source.slice(start, newline), end: newline, next: newline + 1 }
}

function findNextFence(source: string, from: number): FenceBlock | null {
  let lineStart = from
  while (lineStart < source.length) {
    const openingLine = lineAt(source, lineStart)
    const openingMatch = openingLine.text.match(/^\s*```\s*([^\s`]*)?.*$/)

    if (!openingMatch) {
      lineStart = openingLine.next
      continue
    }

    const fenceStart = lineStart
    const language = openingMatch[1] ?? ''
    const contentStart = openingLine.next
    let closeLineStart = contentStart

    while (closeLineStart < source.length) {
      const closingLine = lineAt(source, closeLineStart)
      if (/^\s*```\s*$/.test(closingLine.text)) {
        return {
          start: fenceStart,
          end: closingLine.next,
          language,
          content: source.slice(contentStart, closeLineStart),
          closed: true,
        }
      }
      if (closingLine.next === closeLineStart) break
      closeLineStart = closingLine.next
    }

    return {
      start: fenceStart,
      end: source.length,
      language,
      content: source.slice(contentStart),
      closed: false,
    }
  }

  return null
}

function findBalancedJsonEnd(source: string, start: number): number | null {
  let depth = 0
  let inString = false
  let escaped = false

  for (let i = start; i < source.length; i++) {
    const char = source[i]

    if (inString) {
      if (escaped) {
        escaped = false
      } else if (char === '\\') {
        escaped = true
      } else if (char === '"') {
        inString = false
      }
      continue
    }

    if (char === '"') {
      inString = true
      continue
    }

    if (char === '{' || char === '[') {
      depth++
      continue
    }

    if (char === '}' || char === ']') {
      depth--
      if (depth === 0) return i + 1
      if (depth < 0) return null
    }
  }

  return null
}

function pushText(segments: AssistantMessageSegment[], content: string): void {
  if (!content) return
  const previous = segments[segments.length - 1]
  if (previous?.type === 'text') {
    previous.content += content
  } else {
    segments.push({ type: 'text', content })
  }
}

function pushTextWithInlineJson(segments: AssistantMessageSegment[], content: string): void {
  if (!content) return

  let textStart = 0
  let i = 0

  while (i < content.length) {
    const char = content[i]

    if (char !== '{' && char !== '[') {
      i++
      continue
    }

    const candidateEnd = findBalancedJsonEnd(content, i)
    if (candidateEnd == null) {
      i++
      continue
    }

    const raw = content.slice(i, candidateEnd)
    const parsed = parseJson(raw)
    if (!parsed.ok) {
      i++
      continue
    }

    pushText(segments, content.slice(textStart, i))
    segments.push({ type: 'json', value: parsed.value, raw })
    textStart = candidateEnd
    i = candidateEnd
  }

  pushText(segments, content.slice(textStart))
}

export function parseAssistantMessageContent(content: string): ParsedAssistantMessage {
  const trimmed = content.trim()

  if (!trimmed) {
    return { isPureJson: false, segments: [{ type: 'text', content }] }
  }

  const firstChar = trimmed[0]
  if (firstChar === '{' || firstChar === '[') {
    const parsed = parseJson(trimmed)
    if (parsed.ok) {
      return {
        isPureJson: true,
        segments: [{ type: 'json', value: parsed.value, raw: trimmed }],
      }
    }
  }

  const segments: AssistantMessageSegment[] = []
  let cursor = 0

  while (cursor < content.length) {
    const fence = findNextFence(content, cursor)
    if (!fence) {
      pushTextWithInlineJson(segments, content.slice(cursor))
      break
    }

    pushTextWithInlineJson(segments, content.slice(cursor, fence.start))

    const rawFenceContent = fence.content.trim()
    const parsedFence = fence.closed && isJsonLanguage(fence.language)
      ? parseJson(rawFenceContent)
      : { ok: false as const }

    if (parsedFence.ok) {
      segments.push({ type: 'json', value: parsedFence.value, raw: rawFenceContent })
    } else {
      pushText(segments, content.slice(fence.start, fence.end))
    }

    cursor = fence.end
  }

  if (segments.length === 0) {
    segments.push({ type: 'text', content })
  }

  const isPureJson = segments.length === 1 && segments[0].type === 'json'

  return { isPureJson, segments }
}
