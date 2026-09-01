import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import CodeMirror from '@uiw/react-codemirror'
import { json } from '@codemirror/lang-json'
import { EditorView } from '@codemirror/view'
import { Copy, Check, ChevronDown, ChevronRight, Paintbrush, Maximize2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatJsonSafely } from '@/lib/json-utils'
import { UI_LAYER_CLASS } from '@/lib/ui-layers'
import { jsonDarkTheme, jsonSyntaxHighlight } from './json-cm-theme'

interface JsonCodeBlockProps {
  value?: unknown
  title?: string
  maxHeight?: number | string
  className?: string
  actions?: ('copy' | 'format' | 'collapse' | 'expand')[]
  collapsed?: boolean
}

export function JsonCodeBlock({
  value,
  title,
  maxHeight = 480,
  className,
  actions = ['copy', 'expand'],
  collapsed: initialCollapsed = false,
}: JsonCodeBlockProps) {
  const [collapsed, setCollapsed] = useState(initialCollapsed)
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)

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

  const toggleCollapse = useCallback(() => {
    setCollapsed((c) => !c)
  }, [])

  const handleExpand = useCallback(() => {
    setExpanded(true)
  }, [])

  const handleCloseExpand = useCallback(() => {
    setExpanded(false)
  }, [])

  useEffect(() => {
    if (!expanded) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExpanded(false)
    }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
    }
  }, [expanded])

  const cmExtensions = useMemo(
    () => [json(), jsonDarkTheme, jsonSyntaxHighlight, EditorView.editable.of(false)],
    [],
  )

  const cmBasicSetup = {
    lineNumbers: true,
    foldGutter: true,
    highlightActiveLine: false,
    highlightActiveLineGutter: false,
  }

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
            {actions.includes('expand') && displayText && (
              <button
                onClick={handleExpand}
                className="p-1 rounded text-muted-foreground hover:text-blue-200 hover:bg-accent transition-colors"
                title="Expand JSON"
                aria-label="Expand JSON"
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </button>
            )}
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
                onClick={() => {}}
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
          className="rounded-lg border border-[#24324A] scrollbar-thin overflow-auto"
          style={{ maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight }}
        >
          <CodeMirror
            value={displayText}
            extensions={cmExtensions}
            readOnly
            basicSetup={cmBasicSetup}
            className="cm-custom-scroll"
            theme="none"
          />
        </div>
      )}
      {(!collapsed || !actions.includes('collapse')) && !displayText && (
        <div className="rounded-lg border border-border bg-background px-3 py-4 text-center">
          <p className="text-xs text-muted">No data</p>
        </div>
      )}

      {expanded && createPortal(
        <div
          ref={overlayRef}
          className={`fixed inset-0 ${UI_LAYER_CLASS.focus} flex items-center justify-center bg-[#020617]/72 backdrop-blur-md`}
          onClick={(e) => { if (e.target === overlayRef.current) handleCloseExpand() }}
        >
          <div className="relative flex flex-col w-[95vw] max-w-[1600px] h-[90vh] rounded-xl border border-[#24324A] bg-surface shadow-2xl">
            <div className="flex items-center justify-between shrink-0 px-5 py-4 border-b border-border">
              <span className="text-xs font-medium text-muted truncate">
                {title || 'JSON'}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={handleCopy}
                  className="p-1 rounded-md text-muted hover:text-white hover:bg-accent transition-colors"
                  title={copied ? 'Copied!' : 'Copy'}
                  aria-label="Copy JSON"
                >
                  {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                </button>
                <button
                  onClick={handleCloseExpand}
                  className="p-1 rounded-md text-muted hover:text-white hover:bg-accent transition-colors"
                  aria-label="Close"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="flex-1 min-h-0">
              <CodeMirror
                value={displayText}
                extensions={cmExtensions}
                readOnly
                basicSetup={cmBasicSetup}
                theme="none"
                height="100%"
                className="h-full"
              />
            </div>
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
