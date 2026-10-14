import { useCallback, useMemo, useState, type ReactNode } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { json } from '@codemirror/lang-json'
import { EditorView } from '@codemirror/view'
import { Check, ChevronDown, ChevronRight, Copy, Maximize2, Paintbrush } from 'lucide-react'
import { Button } from './Button'
import { Dialog } from './Dialog'
import { CodePanel } from './CodePanel'
import { EmptyStatePanel } from './EmptyStatePanel'
import { cn } from '../lib/cn'
import { formatJsonSafely } from '../lib/json'
import { jsonDarkTheme, jsonSyntaxHighlight } from '../lib/json-codemirror'
import { woobeLayout, woobeTypographyScale } from '../tokens'

export interface JsonCodeBlockProps {
  value?: unknown
  title?: string
  maxHeight?: number | string
  className?: string
  actions?: ('copy' | 'format' | 'collapse' | 'expand')[]
  collapsed?: boolean
  density?: 'default' | 'compact'
}

const compactJsonTypography = EditorView.theme({
  '.cm-content': {
    fontSize: woobeTypographyScale.codeCompact[0],
    lineHeight: woobeTypographyScale.codeCompact[1].lineHeight,
  },
  '.cm-gutters': {
    fontSize: woobeTypographyScale.systemNano[0],
    lineHeight: woobeTypographyScale.systemNano[1].lineHeight,
  },
})

function ActionButton({ label, title, onClick, children }: { label: string; title: string; onClick: () => void; children: ReactNode }) {
  return <Button type="button" variant="outline" size="sm" onClick={onClick} className="w-control-sm px-0 text-muted-foreground" title={title} aria-label={label}>{children}</Button>
}

export function JsonCodeBlock({
  value,
  title,
  maxHeight = woobeLayout.codeEditorMax,
  className,
  actions = ['copy', 'expand'],
  collapsed: initialCollapsed = false,
  density = 'default',
}: JsonCodeBlockProps) {
  const [collapsed, setCollapsed] = useState(initialCollapsed)
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)

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


  const inlineCmExtensions = useMemo(
    () => [
      json(),
      jsonDarkTheme,
      jsonSyntaxHighlight,
      EditorView.editable.of(false),
      ...(density === 'compact' ? [compactJsonTypography] : []),
    ],
    [density],
  )
  const expandedCmExtensions = useMemo(
    () => [json(), jsonDarkTheme, jsonSyntaxHighlight, EditorView.editable.of(false)],
    [],
  )
  const cmBasicSetup = { lineNumbers: true, foldGutter: true, highlightActiveLine: false, highlightActiveLineGutter: false }
  const visible = !collapsed || !actions.includes('collapse')

  const panelActions = (
    <>
      {actions.includes('collapse') && displayText ? <ActionButton label={collapsed ? 'Expand' : 'Collapse'} title={collapsed ? 'Expand' : 'Collapse'} onClick={() => setCollapsed(current => !current)}>{collapsed ? <ChevronRight className="h-icon-sm w-icon-sm" /> : <ChevronDown className="h-icon-sm w-icon-sm" />}</ActionButton> : null}
      {actions.includes('format') && displayText ? <ActionButton label="Format JSON" title="Format JSON" onClick={() => {}}><Paintbrush className="h-icon-sm w-icon-sm" /></ActionButton> : null}
      {actions.includes('copy') && displayText ? <ActionButton label="Copy JSON" title={copied ? 'Copied!' : 'Copy'} onClick={handleCopy}>{copied ? <Check className="h-icon-sm w-icon-sm text-success" /> : <Copy className="h-icon-sm w-icon-sm" />}</ActionButton> : null}
      {actions.includes('expand') && displayText ? <ActionButton label="Expand JSON" title="Expand JSON" onClick={() => setExpanded(true)}><Maximize2 className="h-icon-sm w-icon-sm" /></ActionButton> : null}
    </>
  )

  return (
    <>
      <CodePanel title={title || 'JSON'} badge={isInvalid ? <span className="text-error">INVALID</span> : 'JSON'} actions={panelActions} density="compact" className={cn(className)}>
        {visible && displayText ? <div className="scrollbar-thin overflow-auto bg-background/20" style={{ maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight }}><CodeMirror value={displayText} extensions={inlineCmExtensions} readOnly basicSetup={cmBasicSetup} className="cm-custom-scroll" theme="none" /></div> : null}
        {visible && !displayText ? <div className="p-ui-md"><EmptyStatePanel compact title="No JSON data" /></div> : null}
      </CodePanel>

      <Dialog open={expanded} onClose={() => setExpanded(false)} title={title || 'JSON'} layer="nestedModal"
        className="flex h-focus-workspace max-w-resource flex-col overflow-hidden" contentClassName="min-h-0 flex-1 p-0">
        <div className="flex justify-end border-b border-border p-ui-sm"><ActionButton label="Copy JSON" title={copied ? 'Copied!' : 'Copy'} onClick={handleCopy}>{copied ? <Check className="h-icon-sm w-icon-sm text-success" /> : <Copy className="h-icon-sm w-icon-sm" />}</ActionButton></div>
        <div className="min-h-0 flex-1 bg-background/20"><CodeMirror value={displayText} extensions={expandedCmExtensions} readOnly basicSetup={cmBasicSetup} theme="none" height="100%" className="h-full" /></div>
      </Dialog>
    </>
  )
}
