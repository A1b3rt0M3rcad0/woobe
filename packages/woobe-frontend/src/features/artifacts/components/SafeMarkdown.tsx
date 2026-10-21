import type { ReactNode } from 'react'

function safeHref(value: string): string | null {
  try {
    const url = new URL(value)
    return ['https:', 'http:', 'mailto:'].includes(url.protocol) ? url.href : null
  } catch {
    return null
  }
}

function inline(text: string): ReactNode[] {
  const parts: ReactNode[] = []
  const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g
  let offset = 0
  for (const match of text.matchAll(linkPattern)) {
    const index = match.index ?? 0
    if (index > offset) parts.push(text.slice(offset, index))
    const href = safeHref(match[2])
    parts.push(href
      ? <a key={`${index}-${match[1]}`} href={href} target="_blank" rel="noopener noreferrer" className="underline">{match[1]}</a>
      : match[0])
    offset = index + match[0].length
  }
  if (offset < text.length) parts.push(text.slice(offset))
  return parts
}

/** Small safe Markdown subset; raw HTML is always rendered as text. */
export function SafeMarkdown({ source }: { source: string }) {
  const lines = source.split(/\r?\n/)
  const blocks: ReactNode[] = []
  let paragraph: string[] = []
  let code: string[] | null = null
  let list: string[] = []

  const flushParagraph = () => {
    if (paragraph.length) blocks.push(<p key={`p-${blocks.length}`}>{inline(paragraph.join(' '))}</p>)
    paragraph = []
  }
  const flushList = () => {
    if (list.length) blocks.push(<ul key={`ul-${blocks.length}`} className="list-disc pl-ui-lg">{list.map((item, index) => <li key={index}>{inline(item)}</li>)}</ul>)
    list = []
  }

  for (const line of lines) {
    if (line.startsWith('```')) {
      flushParagraph(); flushList()
      if (code) {
        blocks.push(<pre key={`code-${blocks.length}`} className="overflow-auto rounded-technical bg-muted/50 p-ui-sm"><code>{code.join('\n')}</code></pre>)
        code = null
      } else code = []
      continue
    }
    if (code) { code.push(line); continue }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line)
    if (heading) {
      flushParagraph(); flushList()
      const level = heading[1].length
      const text = heading[2]
      const className = level < 3 ? 'text-title-md font-semibold' : 'font-semibold'
      blocks.push(level === 1 ? <h1 key={`h-${blocks.length}`} className={className}>{inline(text)}</h1>
        : level === 2 ? <h2 key={`h-${blocks.length}`} className={className}>{inline(text)}</h2>
          : level === 3 ? <h3 key={`h-${blocks.length}`} className={className}>{inline(text)}</h3>
            : <h4 key={`h-${blocks.length}`} className={className}>{inline(text)}</h4>)
      continue
    }
    const bullet = /^\s*[-*+]\s+(.+)$/.exec(line)
    if (bullet) { flushParagraph(); list.push(bullet[1]); continue }
    if (!line.trim()) { flushParagraph(); flushList(); continue }
    flushList()
    paragraph.push(line.trim())
  }
  flushParagraph(); flushList()
  if (code) blocks.push(<pre key={`code-${blocks.length}`} className="overflow-auto rounded-technical bg-muted/50 p-ui-sm"><code>{code.join('\n')}</code></pre>)
  return <div className="grid min-w-0 gap-ui-md break-words leading-relaxed">{blocks}</div>
}
