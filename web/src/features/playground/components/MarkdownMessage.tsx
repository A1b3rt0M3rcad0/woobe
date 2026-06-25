import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface MarkdownMessageProps {
  content: string
  isStreaming?: boolean
  className?: string
}

type PendingList = {
  ordered: boolean
  items: string[]
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const pattern = /(\[([^\]]+)\]\((https?:\/\/[^)\s]+)\))|(`([^`]+)`)|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)|(https?:\/\/[^\s<]+)/g
  let lastIndex = 0
  let index = 0

  const pushText = (value: string) => {
    if (!value) return
    const parts = value.split('\n')
    parts.forEach((part, partIndex) => {
      if (part) nodes.push(part)
      if (partIndex < parts.length - 1) {
        nodes.push(<br key={`${keyPrefix}-br-${index++}`} />)
      }
    })
  }

  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0
    pushText(text.slice(lastIndex, start))

    if (match[2] && match[3]) {
      nodes.push(
        <a
          key={`${keyPrefix}-link-${index++}`}
          href={match[3]}
          target="_blank"
          rel="noreferrer noopener"
          className="text-primary underline underline-offset-2 hover:text-primary/80"
        >
          {match[2]}
        </a>,
      )
    } else if (match[5]) {
      nodes.push(
        <code
          key={`${keyPrefix}-code-${index++}`}
          className="rounded bg-background/70 px-1 py-0.5 font-mono text-[0.85em] text-slate-200"
        >
          {match[5]}
        </code>,
      )
    } else if (match[7]) {
      nodes.push(<strong key={`${keyPrefix}-bold-${index++}`}>{match[7]}</strong>)
    } else if (match[9]) {
      nodes.push(<em key={`${keyPrefix}-italic-${index++}`}>{match[9]}</em>)
    } else if (match[10]) {
      nodes.push(
        <a
          key={`${keyPrefix}-url-${index++}`}
          href={match[10]}
          target="_blank"
          rel="noreferrer noopener"
          className="text-primary underline underline-offset-2 hover:text-primary/80"
        >
          {match[10]}
        </a>,
      )
    }

    lastIndex = start + match[0].length
  }

  pushText(text.slice(lastIndex))
  return nodes
}

export function MarkdownMessage({ content, isStreaming, className }: MarkdownMessageProps) {
  const blocks: ReactNode[] = []
  const lines = content.replace(/\r\n/g, '\n').split('\n')
  let paragraph: string[] = []
  let pendingList: PendingList | null = null
  let codeFence: { language: string; lines: string[] } | null = null
  let key = 0

  const flushParagraph = () => {
    if (!paragraph.length) return
    const value = paragraph.join('\n')
    const currentKey = key++
    blocks.push(
      <p key={`p-${currentKey}`} className="leading-relaxed">
        {renderInline(value, `p-${currentKey}`)}
      </p>,
    )
    paragraph = []
  }

  const flushList = () => {
    if (!pendingList) return
    const currentKey = key++
    const ListTag = pendingList.ordered ? 'ol' : 'ul'
    blocks.push(
      <ListTag
        key={`list-${currentKey}`}
        className={cn(
          'space-y-1 pl-5 leading-relaxed',
          pendingList.ordered ? 'list-decimal' : 'list-disc',
        )}
      >
        {pendingList.items.map((item, itemIndex) => (
          <li key={`list-${currentKey}-${itemIndex}`}>
            {renderInline(item, `list-${currentKey}-${itemIndex}`)}
          </li>
        ))}
      </ListTag>,
    )
    pendingList = null
  }

  const flushCode = () => {
    if (!codeFence) return
    const currentKey = key++
    const language = codeFence.language.trim()
    blocks.push(
      <pre
        key={`code-${currentKey}`}
        className="my-2 overflow-x-auto rounded-lg border border-border bg-background/80 px-3 py-2 text-xs leading-relaxed text-slate-200"
      >
        <code data-language={language || undefined}>{codeFence.lines.join('\n')}</code>
      </pre>,
    )
    codeFence = null
  }

  for (const line of lines) {
    const fenceMatch = line.match(/^\s*```\s*([\w-]+)?\s*$/)
    if (fenceMatch) {
      if (codeFence) {
        flushCode()
      } else {
        flushParagraph()
        flushList()
        codeFence = { language: fenceMatch[1] ?? '', lines: [] }
      }
      continue
    }

    if (codeFence) {
      codeFence.lines.push(line)
      continue
    }

    if (!line.trim()) {
      flushParagraph()
      flushList()
      continue
    }

    const headingMatch = line.match(/^(#{1,3})\s+(.+)$/)
    if (headingMatch) {
      flushParagraph()
      flushList()
      const level = headingMatch[1].length
      const text = headingMatch[2]
      const currentKey = key++
      const HeadingTag = (`h${level}` as 'h1' | 'h2' | 'h3')
      blocks.push(
        <HeadingTag
          key={`h-${currentKey}`}
          className={cn(
            'font-semibold leading-tight text-white',
            level === 1 && 'text-lg mt-1',
            level === 2 && 'text-base mt-1',
            level === 3 && 'text-sm mt-1',
          )}
        >
          {renderInline(text, `h-${currentKey}`)}
        </HeadingTag>,
      )
      continue
    }

    const quoteMatch = line.match(/^>\s?(.*)$/)
    if (quoteMatch) {
      flushParagraph()
      flushList()
      const currentKey = key++
      blocks.push(
        <blockquote
          key={`quote-${currentKey}`}
          className="border-l-2 border-primary/60 pl-3 text-muted leading-relaxed"
        >
          {renderInline(quoteMatch[1], `quote-${currentKey}`)}
        </blockquote>,
      )
      continue
    }

    const unorderedMatch = line.match(/^\s*[-*]\s+(.+)$/)
    const orderedMatch = line.match(/^\s*\d+\.\s+(.+)$/)
    if (unorderedMatch || orderedMatch) {
      flushParagraph()
      const ordered = Boolean(orderedMatch)
      const item = (orderedMatch?.[1] ?? unorderedMatch?.[1] ?? '').trim()
      if (!pendingList || pendingList.ordered !== ordered) {
        flushList()
        pendingList = { ordered, items: [] }
      }
      pendingList.items.push(item)
      continue
    }

    if (pendingList) flushList()
    paragraph.push(line)
  }

  flushParagraph()
  flushList()
  flushCode()

  return (
    <div className={cn('space-y-2 break-words', className)}>
      {blocks.length > 0 ? blocks : <p>{content}</p>}
      {isStreaming && (
        <span className="inline-flex h-3 w-1.5 translate-y-0.5 animate-pulse rounded-sm bg-primary/80" aria-label="Streaming" />
      )}
    </div>
  )
}
