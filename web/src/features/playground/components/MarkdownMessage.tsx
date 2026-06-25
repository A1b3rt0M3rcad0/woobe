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

type MarkdownTable = {
  headers: string[]
  rows: string[][]
  alignments: Array<'left' | 'center' | 'right'>
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
          className="rounded-md border border-primary/20 bg-primary/10 px-1.5 py-0.5 font-mono text-[0.82em] font-medium text-primary-foreground shadow-[inset_0_0_0_1px_rgba(255,255,255,0.03)]"
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

function isHorizontalRule(line: string): boolean {
  return /^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)
}

function looksLikeTableRow(line: string): boolean {
  const trimmed = line.trim()
  return trimmed.includes('|') && trimmed.replace(/\|/g, '').trim().length > 0
}

function splitTableCells(line: string): string[] {
  const trimmed = line.trim()
  const withoutOuterPipes = trimmed.replace(/^\|/, '').replace(/\|$/, '')
  const cells: string[] = []
  let current = ''
  let escaped = false

  for (const char of withoutOuterPipes) {
    if (escaped) {
      current += char
      escaped = false
      continue
    }

    if (char === '\\') {
      escaped = true
      continue
    }

    if (char === '|') {
      cells.push(current.trim())
      current = ''
      continue
    }

    current += char
  }

  cells.push(current.trim())
  return cells
}

function parseTableSeparator(line: string, columnCount: number): MarkdownTable['alignments'] | null {
  if (!looksLikeTableRow(line)) return null
  const cells = splitTableCells(line)
  if (cells.length !== columnCount) return null

  const alignments: MarkdownTable['alignments'] = []
  for (const rawCell of cells) {
    const cell = rawCell.replace(/\s/g, '')
    if (!/^:?-{3,}:?$/.test(cell)) return null
    const left = cell.startsWith(':')
    const right = cell.endsWith(':')
    alignments.push(left && right ? 'center' : right ? 'right' : 'left')
  }
  return alignments
}

function parseTableAt(lines: string[], startIndex: number): { table: MarkdownTable; endIndex: number } | null {
  const headerLine = lines[startIndex]
  const separatorLine = lines[startIndex + 1]
  if (!headerLine || !separatorLine || !looksLikeTableRow(headerLine)) return null

  const headers = splitTableCells(headerLine)
  if (headers.length < 2) return null

  const alignments = parseTableSeparator(separatorLine, headers.length)
  if (!alignments) return null

  const rows: string[][] = []
  let cursor = startIndex + 2

  while (cursor < lines.length && looksLikeTableRow(lines[cursor])) {
    const cells = splitTableCells(lines[cursor])
    if (cells.length !== headers.length) break
    rows.push(cells)
    cursor++
  }

  return {
    table: { headers, rows, alignments },
    endIndex: cursor,
  }
}

function alignmentClass(alignment: 'left' | 'center' | 'right'): string {
  if (alignment === 'center') return 'text-center'
  if (alignment === 'right') return 'text-right'
  return 'text-left'
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

  const pushHorizontalRule = () => {
    const currentKey = key++
    blocks.push(
      <hr
        key={`hr-${currentKey}`}
        className="my-3 border-0 border-t border-border/80"
      />,
    )
  }

  const pushTable = (table: MarkdownTable) => {
    const currentKey = key++
    blocks.push(
      <div key={`table-${currentKey}`} className="my-3 overflow-x-auto rounded-lg border border-border bg-background/35">
        <table className="min-w-full border-collapse text-xs leading-relaxed">
          <thead className="bg-surface/70 text-muted">
            <tr>
              {table.headers.map((header, headerIndex) => (
                <th
                  key={`table-${currentKey}-h-${headerIndex}`}
                  className={cn(
                    'border-b border-border px-3 py-2 font-semibold uppercase tracking-wide',
                    alignmentClass(table.alignments[headerIndex] ?? 'left'),
                  )}
                >
                  {renderInline(header, `table-${currentKey}-h-${headerIndex}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, rowIndex) => (
              <tr key={`table-${currentKey}-r-${rowIndex}`} className="border-b border-border/60 last:border-b-0">
                {row.map((cell, cellIndex) => (
                  <td
                    key={`table-${currentKey}-r-${rowIndex}-c-${cellIndex}`}
                    className={cn(
                      'min-w-[9rem] px-3 py-2 align-top text-white/90',
                      alignmentClass(table.alignments[cellIndex] ?? 'left'),
                    )}
                  >
                    {renderInline(cell, `table-${currentKey}-r-${rowIndex}-c-${cellIndex}`)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    )
  }

  for (let lineIndex = 0; lineIndex < lines.length; lineIndex++) {
    const line = lines[lineIndex]
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

    if (isHorizontalRule(line)) {
      flushParagraph()
      flushList()
      pushHorizontalRule()
      continue
    }

    const table = parseTableAt(lines, lineIndex)
    if (table) {
      flushParagraph()
      flushList()
      pushTable(table.table)
      lineIndex = table.endIndex - 1
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
