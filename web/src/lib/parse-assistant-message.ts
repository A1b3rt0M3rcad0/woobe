export type AssistantMessageSegment =
  | { type: 'text'; content: string }
  | { type: 'json'; value: unknown; raw: string }

export interface ParsedAssistantMessage {
  isPureJson: boolean
  segments: AssistantMessageSegment[]
}

export function parseAssistantMessageContent(content: string): ParsedAssistantMessage {
  const trimmed = content.trim()

  if (!trimmed) {
    return { isPureJson: false, segments: [{ type: 'text', content }] }
  }

  const firstChar = trimmed[0]
  if (firstChar === '{' || firstChar === '[') {
    try {
      const value = JSON.parse(trimmed)
      return {
        isPureJson: true,
        segments: [{ type: 'json', value, raw: trimmed }],
      }
    } catch {
      // Not pure JSON, fall through to scanning
    }
  }

  const segments: AssistantMessageSegment[] = []
  let textStart = 0
  let i = 0
  const len = content.length

  while (i < len) {
    const char = content[i]

    if (char === '{' || char === '[') {
      const candidateStart = i
      let depth = 1
      i++

      while (i < len && depth > 0) {
        const c = content[i]
        if (c === '{' || c === '[') depth++
        else if (c === '}' || c === ']') depth--
        i++
      }

      if (depth === 0) {
        const raw = content.slice(candidateStart, i)

        try {
          const value = JSON.parse(raw)

          const textBefore = content.slice(textStart, candidateStart)
          if (textBefore) {
            segments.push({ type: 'text', content: textBefore })
          }

          segments.push({ type: 'json', value, raw })
          textStart = i
        } catch {
          // Invalid JSON — keep walking, the raw text will be part of the
          // trailing text segment
        }
      }
      // depth > 0 means unbalanced braces — exit the loop and flush
      // everything remaining as text
    } else {
      i++
    }
  }

  const remaining = content.slice(textStart)
  if (remaining) {
    segments.push({ type: 'text', content: remaining })
  }

  if (segments.length === 0) {
    segments.push({ type: 'text', content })
  }

  const isPureJson = segments.length === 1 && segments[0].type === 'json'

  return { isPureJson, segments }
}
