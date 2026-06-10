import { useState, useMemo, useCallback } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { json } from '@codemirror/lang-json'
import { EditorView } from '@codemirror/view'
import { Copy, Check, ChevronDown, ChevronRight, Paintbrush } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatJsonSafely } from '@/lib/json-utils'

const darkTheme = EditorView.theme(
  {
    '&': { backgroundColor: '#020817', color: '#e2e8f0' },
    '.cm-content': {
      caretColor: '#3b82f6',
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      fontSize: '12px',
      lineHeight: '1.6',
    },
    '.cm-cursor': { borderLeftColor: '#3b82f6' },
    '.cm-gutters': { backgroundColor: '#020817', borderRight: '1px solid #1e293b', color: '#475569' },
    '.cm-activeLine': { backgroundColor: '#0f1729' },
    '.cm-activeLineGutter': { backgroundColor: '#0f1729' },
    '&.cm-focused': { outline: 'none' },
    '.cm-selectionBackground': { backgroundColor: '#1e40af40' },
    '.cm-matchingBracket': { backgroundColor: '#1e293b', outline: '1px solid #334155' },
    '.cm-scroller::-webkit-scrollbar': { width: '5px', height: '5px' },
    '.cm-scroller::-webkit-scrollbar-track': { background: 'transparent' },
    '.cm-scroller::-webkit-scrollbar-thumb': { backgroundColor: 'rgba(148, 163, 184, 0.15)', borderRadius: '999px' },
    '.cm-scroller::-webkit-scrollbar-thumb:hover': { backgroundColor: 'rgba(148, 163, 184, 0.35)' },
    '.cm-scroller::-webkit-scrollbar-corner': { background: 'transparent' },
  },
  { dark: true },
)

const jsonHighlight = EditorView.theme(
  {
    '.ͼ1 .cm-atom': { color: '#c084fc' },
    '.ͼ1 .cm-number': { color: '#fbbf24' },
    '.ͼ1 .cm-string': { color: '#4ade80' },
    '.ͼ1 .cm-keyword': { color: '#f87171' },
    '.ͼ6': { color: '#f87171' },
    '.ͼ10 .cm-atom': { color: '#c084fc' },
    '.ͼ12 .cm-atom': { color: '#c084fc' },
    'span.ͼ1': { color: '#60a5fa' },
  },
)

interface JsonCodeBlockProps {
  value?: unknown
  title?: string
  maxHeight?: number | string
  className?: string
  actions?: ('copy' | 'format' | 'collapse')[]
  collapsed?: boolean
}

export function JsonCodeBlock({
  value,
  title,
  maxHeight = 480,
  className,
  actions = ['copy'],
  collapsed: initialCollapsed = false,
}: JsonCodeBlockProps) {
  const [collapsed, setCollapsed] = useState(initialCollapsed)
  const [copied, setCopied] = useState(false)

  const rawText = useMemo(() => {
    if (value == null) return ''
    if (typeof value === 'string') return value
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }, [value])

  const displayText = useMemo(() => {
    if (!rawText) return ''
    const result = formatJsonSafely(rawText)
    return result.ok ? result.value : rawText
  }, [rawText])

  const isInvalid = useMemo(() => {
    if (!rawText) return false
    if (typeof value === 'object' && value !== null) return false
    const result = formatJsonSafely(rawText)
    return !result.ok
  }, [rawText, value])

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(displayText)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }, [displayText])

  const handleFormat = useCallback(() => {
  }, [])

  const toggleCollapse = useCallback(() => {
    setCollapsed((c) => !c)
  }, [])

  const hasTitle = title || actions.length > 0 || isInvalid

  return (
    <div className={cn('space-y-2', className)}>
      {hasTitle && (
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            {title && (
              <span className="text-xs font-medium text-muted truncate">{title}</span>
            )}
            {isInvalid && (
              <span className="text-[10px] font-medium text-rose-400 shrink-0">Invalid JSON</span>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {actions.includes('collapse') && displayText && (
              <button
                onClick={toggleCollapse}
                className="p-1 rounded text-muted hover:text-white hover:bg-accent transition-colors"
                title={collapsed ? 'Expand' : 'Collapse'}
              >
                {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </button>
            )}
            {actions.includes('format') && displayText && (
              <button
                onClick={handleFormat}
                className="p-1 rounded text-muted hover:text-white hover:bg-accent transition-colors"
                title="Format JSON"
              >
                <Paintbrush className="h-3.5 w-3.5" />
              </button>
            )}
            {actions.includes('copy') && displayText && (
              <button
                onClick={handleCopy}
                className="p-1 rounded text-muted hover:text-white hover:bg-accent transition-colors"
                title={copied ? 'Copied!' : 'Copy'}
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            )}
          </div>
        </div>
      )}
      {(!collapsed || !actions.includes('collapse')) && displayText && (
        <div
          className="rounded-lg border border-border scrollbar-thin overflow-auto"
          style={{ maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight }}
        >
          <CodeMirror
            value={displayText}
            extensions={[json(), darkTheme, jsonHighlight, EditorView.editable.of(false)]}
            readOnly
            basicSetup={{
              lineNumbers: false,
              foldGutter: false,
              highlightActiveLine: false,
              highlightActiveLineGutter: false,
            }}
            className="cm-custom-scroll"
            theme="dark"
          />
        </div>
      )}
      {(!collapsed || !actions.includes('collapse')) && !displayText && (
        <div className="rounded-lg border border-border bg-background px-3 py-4 text-center">
          <p className="text-xs text-muted">No data</p>
        </div>
      )}
    </div>
  )
}
