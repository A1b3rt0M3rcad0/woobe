import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

import { MathExpression } from './MathExpression'

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

type DisplayMathBlock = {
  expression: string
  endIndex: number
}

type InlineRenderContext = 'body' | 'table'

function inlineCodeClass(context: InlineRenderContext): string {
  if (context === 'table') {
    return 'rounded-technical border border-border/80 bg-surface/70 px-ui-sm py-ui-hairline font-mono text-[0.82em] font-medium leading-none text-slate-100'
  }

  return 'rounded-technical border border-white/10 bg-white/[0.06] px-ui-xs py-ui-hairline font-mono text-[0.86em] font-medium leading-none text-slate-100'
}

function isEscaped(value: string, index: number): boolean {
  let backslashes = 0
  for (let cursor = index - 1; cursor >= 0 && value[cursor] === '\\'; cursor--) backslashes += 1
  return backslashes % 2 === 1
}

function looksLikeDollarMath(value: string): boolean {
  const expression = value.trim()
  if (!expression || expression.length > 500) return false
  if (/\\[A-Za-z]+/.test(expression)) return true
  if (/[\^_={}<>±×÷∫∑√]/u.test(expression)) return true
  if (/[+\-*/=]/.test(expression)) return true
  if (/^[A-Za-zΑ-ω]$/u.test(expression)) return true
  return /^(?:\d+(?:\.\d+)?)?[A-Za-zΑ-ω]+(?:\d+)?$/u.test(expression)
}

function renderInline(
  text: string,
  keyPrefix: string,
  context: InlineRenderContext = 'body',
  depth = 0,
): ReactNode[] {
  if (depth > 4) return [text]

  const nodes: ReactNode[] = []
  const pattern = /(\\\((.+?)\\\))|(\$([^$\n]+?)\$)|(\[([^\]]+)\]\((https?:\/\/[^)\s]+)\))|(`([^`]+)`)|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)|(https?:\/\/[^\s<]+)/g
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

    if (match[1] && match[2]) {
      nodes.push(
        <MathExpression
          key={`${keyPrefix}-math-${index++}`}
          expression={match[2]}
        />,
      )
    } else if (match[3] && match[4]) {
      const closeIndex = start + match[0].length - 1
      if (isEscaped(text, start) || isEscaped(text, closeIndex) || !looksLikeDollarMath(match[4])) {
        pushText(match[0])
      } else {
        nodes.push(
          <MathExpression
            key={`${keyPrefix}-math-${index++}`}
            expression={match[4]}
          />,
        )
      }
    } else if (match[6] && match[7]) {
      nodes.push(
        <a
          key={`${keyPrefix}-link-${index++}`}
          href={match[7]}
          target="_blank"
          rel="noreferrer noopener"
          className="text-primary underline underline-offset-2 hover:text-primary/80"
        >
          {renderInline(match[6], `${keyPrefix}-link-label-${index}`, context, depth + 1)}
        </a>,
      )
    } else if (match[9]) {
      nodes.push(
        <code
          key={`${keyPrefix}-code-${index++}`}
          className={inlineCodeClass(context)}
        >
          {match[9]}
        </code>,
      )
    } else if (match[11]) {
      const nestedKey = `${keyPrefix}-bold-${index++}`
      nodes.push(
        <strong key={nestedKey}>
          {renderInline(match[11], nestedKey, context, depth + 1)}
        </strong>,
      )
    } else if (match[13]) {
      const nestedKey = `${keyPrefix}-italic-${index++}`
      nodes.push(
        <em key={nestedKey}>
          {renderInline(match[13], nestedKey, context, depth + 1)}
        </em>,
      )
    } else if (match[14]) {
      nodes.push(
        <a
          key={`${keyPrefix}-url-${index++}`}
          href={match[14]}
          target="_blank"
          rel="noreferrer noopener"
          className="text-primary underline underline-offset-2 hover:text-primary/80"
        >
          {match[14]}
        </a>,
      )
    }

    lastIndex = start + match[0].length
  }

  pushText(text.slice(lastIndex))
  return nodes
}

function parseDisplayMathAt(lines: string[], startIndex: number): DisplayMathBlock | null {
  const firstLine = lines[startIndex]
  const trimmed = firstLine.trim()
  const opening = trimmed.startsWith('$$') ? '$$' : trimmed.startsWith('\\[') ? '\\[' : null
  if (!opening) return null

  const closing = opening === '$$' ? '$$' : '\\]'
  const firstContent = trimmed.slice(opening.length)
  const sameLineClose = firstContent.indexOf(closing)

  if (sameLineClose >= 0) {
    const remainder = firstContent.slice(sameLineClose + closing.length)
    if (remainder.trim()) return null
    return {
      expression: firstContent.slice(0, sameLineClose).trim(),
      endIndex: startIndex,
    }
  }

  const expressionLines = firstContent ? [firstContent] : []
  for (let cursor = startIndex + 1; cursor < lines.length; cursor++) {
    const line = lines[cursor]
    const closeIndex = line.indexOf(closing)
    if (closeIndex < 0) {
      expressionLines.push(line)
      continue
    }

    const remainder = line.slice(closeIndex + closing.length)
    if (remainder.trim()) return null
    expressionLines.push(line.slice(0, closeIndex))
    return {
      expression: expressionLines.join('\n').trim(),
      endIndex: cursor,
    }
  }

  return null
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

  for (let index = 0; index < withoutOuterPipes.length; index++) {
    const char = withoutOuterPipes[index]
    const next = withoutOuterPipes[index + 1]

    if (char === '\\' && next === '|') {
      current += '|'
      index += 1
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

export function MarkdownMessage({ content, className }: MarkdownMessageProps) {
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
          'space-y-ui-xs pl-ui-xl leading-relaxed',
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
        className="my-ui-sm overflow-x-auto rounded-container border border-border bg-background/80 px-ui-md py-ui-sm font-mono text-system-control text-slate-200"
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
        className="my-ui-md border-0 border-t border-border/80"
      />,
    )
  }

  const pushDisplayMath = (expression: string) => {
    const currentKey = key++
    blocks.push(
      <MathExpression
        key={`math-${currentKey}`}
        expression={expression}
        display
      />,
    )
  }

  const pushTable = (table: MarkdownTable) => {
    const currentKey = key++
    blocks.push(
      <div key={`table-${currentKey}`} className="my-ui-md overflow-x-auto rounded-container border border-border bg-background/35">
        <table className="min-w-full border-collapse font-sans text-product-small">
          <thead className="bg-surface/70 font-mono text-system-label text-muted-foreground">
            <tr>
              {table.headers.map((header, headerIndex) => (
                <th
                  key={`table-${currentKey}-h-${headerIndex}`}
                  className={cn(
                    'border-b border-border px-ui-md py-ui-sm font-semibold uppercase tracking-wide',
                    alignmentClass(table.alignments[headerIndex] ?? 'left'),
                  )}
                >
                  {renderInline(header, `table-${currentKey}-h-${headerIndex}`, 'table')}
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
                      'min-w-content-table-cell px-ui-md py-ui-sm align-top text-white/90',
                      alignmentClass(table.alignments[cellIndex] ?? 'left'),
                    )}
                  >
                    {renderInline(cell, `table-${currentKey}-r-${rowIndex}-c-${cellIndex}`, 'table')}
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

    const displayMath = parseDisplayMathAt(lines, lineIndex)
    if (displayMath) {
      flushParagraph()
      flushList()
      pushDisplayMath(displayMath.expression)
      lineIndex = displayMath.endIndex
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
            'mt-ui-xs font-sans font-semibold text-slate-50',
            level === 1 && 'text-heading-lg',
            level === 2 && 'text-heading',
            level === 3 && 'text-heading-sm',
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
          className="border-l-2 border-primary/60 pl-ui-md font-sans text-muted-foreground"
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
    <div className={cn('space-y-ui-sm break-words', className)}>
      {blocks.length > 0 ? blocks : <p>{content}</p>}
    </div>
  )
}
