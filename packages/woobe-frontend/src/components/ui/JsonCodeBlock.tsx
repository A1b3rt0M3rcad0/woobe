import { useState, useMemo, useCallback, useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import CodeMirror from '@uiw/react-codemirror'
import { json } from '@codemirror/lang-json'
import { EditorView } from '@codemirror/view'
import { Check, ChevronDown, ChevronRight, Copy, Maximize2, Paintbrush, X } from 'lucide-react'
import { CodePanel, EmptyStatePanel } from '@woobe/ui'
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

function ActionButton({ label, title, onClick, children }: { label: string; title: string; onClick: () => void; children: ReactNode }) {
  return <button type="button" onClick={onClick} className="flex h-7 w-7 items-center justify-center rounded-control border border-border bg-control/30 text-muted-foreground transition-colors hover:bg-control hover:text-slate-50" title={title} aria-label={label}>{children}</button>
}

export function JsonCodeBlock({
  value,
  title,
  maxHeight = 360,
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
    try { return JSON.stringify(value, null, 2) } catch { return String(value) }
  }, [value])

  const displayText = useMemo(() => {
    if (!rawText) return ''
    const result = formatJsonSafely(rawText)
    return result.ok ? result.value : rawText
  }, [rawText])

  const isInvalid = useMemo(() => {
    if (!rawText) return false
    if (typeof value === 'object' && value !== null) return false
    return !formatJsonSafely(rawText).ok
  }, [rawText, value])

  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(displayText)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }, [displayText])

  useEffect(() => {
    if (!expanded) return
    const handler = (event: KeyboardEvent) => { if (event.key === 'Escape') setExpanded(false) }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
    }
  }, [expanded])

  const cmExtensions = useMemo(() => [json(), jsonDarkTheme, jsonSyntaxHighlight, EditorView.editable.of(false)], [])
  const cmBasicSetup = { lineNumbers: true, foldGutter: true, highlightActiveLine: false, highlightActiveLineGutter: false }
  const visible = !collapsed || !actions.includes('collapse')

  const panelActions = (
    <>
      {actions.includes('collapse') && displayText ? <ActionButton label={collapsed ? 'Expand' : 'Collapse'} title={collapsed ? 'Expand' : 'Collapse'} onClick={() => setCollapsed(value => !value)}>{collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}</ActionButton> : null}
      {actions.includes('format') && displayText ? <ActionButton label="Format JSON" title="Format JSON" onClick={() => {}}><Paintbrush className="h-3 w-3" /></ActionButton> : null}
      {actions.includes('copy') && displayText ? <ActionButton label="Copy JSON" title={copied ? 'Copied!' : 'Copy'} onClick={handleCopy}>{copied ? <Check className="h-3 w-3 text-emerald-300" /> : <Copy className="h-3 w-3" />}</ActionButton> : null}
      {actions.includes('expand') && displayText ? <ActionButton label="Expand JSON" title="Expand JSON" onClick={() => setExpanded(true)}><Maximize2 className="h-3 w-3" /></ActionButton> : null}
    </>
  )

  return (
    <>
      <CodePanel title={title || 'JSON'} badge={isInvalid ? <span className="text-red-300">INVALID</span> : 'JSON'} actions={panelActions} density="compact" className={cn(className)}>
        {visible && displayText ? <div className="scrollbar-thin overflow-auto bg-background/20" style={{ maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight }}><CodeMirror value={displayText} extensions={cmExtensions} readOnly basicSetup={cmBasicSetup} className="cm-custom-scroll" theme="none" /></div> : null}
        {visible && !displayText ? <div className="p-3"><EmptyStatePanel compact title="No JSON data" /></div> : null}
      </CodePanel>

      {expanded && createPortal(
        <div ref={overlayRef} className={`fixed inset-0 ${UI_LAYER_CLASS.focus} flex items-center justify-center bg-background/82 p-4 backdrop-blur-[2px]`} onClick={(event) => { if (event.target === overlayRef.current) setExpanded(false) }}>
          <div role="dialog" aria-modal="true" aria-label={title || 'JSON'} className="flex h-[min(88svh,920px)] w-[min(94vw,1500px)] flex-col overflow-hidden rounded-container border border-border bg-surface">
            <div className="flex min-h-[44px] shrink-0 items-center justify-between border-b border-border px-3">
              <div className="flex min-w-0 items-center gap-2"><span className="truncate font-mono text-[10px] font-semibold text-slate-50">{title || 'Raw JSON'}</span><span className="rounded-technical border border-primary/25 bg-primary/[0.08] px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-[0.08em] text-primary-light">JSON</span></div>
              <div className="flex items-center gap-1"><ActionButton label="Copy JSON" title={copied ? 'Copied!' : 'Copy'} onClick={handleCopy}>{copied ? <Check className="h-3 w-3 text-emerald-300" /> : <Copy className="h-3 w-3" />}</ActionButton><ActionButton label="Close" title="Close" onClick={() => setExpanded(false)}><X className="h-3 w-3" /></ActionButton></div>
            </div>
            <div className="min-h-0 flex-1 bg-background/20"><CodeMirror value={displayText} extensions={cmExtensions} readOnly basicSetup={cmBasicSetup} theme="none" height="100%" className="h-full" /></div>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
