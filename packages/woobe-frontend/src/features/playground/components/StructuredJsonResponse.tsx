import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { json } from '@codemirror/lang-json'
import { EditorView } from '@codemirror/view'
import { Braces, Check, Copy, Maximize2, X } from 'lucide-react'
import { Button, CodePanel, EmptyStatePanel, woobeLayout, woobeTypographyScale } from '@woobe/ui'

import { jsonDarkTheme, jsonSyntaxHighlight } from '@/components/ui/json-cm-theme'
import { cn } from '@/lib/utils'

interface StructuredJsonResponseProps {
  value: unknown
  raw?: string
  maxHeight?: number | string
  className?: string
  density?: 'comfortable' | 'compact'
}

const chatInlineJsonTypography = EditorView.theme({
  '.cm-content': {
    fontSize: woobeTypographyScale.codeCompact[0],
    lineHeight: woobeTypographyScale.codeCompact[1].lineHeight,
  },
  '.cm-gutters': {
    fontSize: woobeTypographyScale.systemNano[0],
    lineHeight: woobeTypographyScale.systemNano[1].lineHeight,
  },
})

const expandedJsonTypography = EditorView.theme({
  '.cm-content': {
    fontSize: woobeTypographyScale.codeDefault[0],
    lineHeight: woobeTypographyScale.codeDefault[1].lineHeight,
  },
  '.cm-gutters': {
    fontSize: woobeTypographyScale.systemMicro[0],
    lineHeight: woobeTypographyScale.systemMicro[1].lineHeight,
  },
})

function IconButton({
  label,
  title,
  onClick,
  children,
}: {
  label: string
  title: string
  onClick: () => void
  children: ReactNode
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={onClick}
      className="w-control-sm px-0 text-muted-foreground"
      title={title}
      aria-label={label}
    >
      {children}
    </Button>
  )
}

export function StructuredJsonResponse({
  value,
  maxHeight,
  className,
  density = 'comfortable',
}: StructuredJsonResponseProps) {
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)
  const compact = density === 'compact'
  const resolvedMaxHeight = maxHeight ?? (compact ? woobeLayout.codeStructuredCompact : woobeLayout.codeStructuredDefault)

  const displayText = useMemo(() => {
    if (value == null) return ''
    if (typeof value === 'string') return value
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }, [value])

  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(displayText)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }, [displayText])

  useEffect(() => {
    if (!expanded) return
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setExpanded(false)
    }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
    }
  }, [expanded])

  const inlineCmExtensions = useMemo(
    () => [
      json(),
      jsonDarkTheme,
      jsonSyntaxHighlight,
      EditorView.editable.of(false),
      ...(!compact ? [chatInlineJsonTypography] : []),
    ],
    [compact],
  )
  const expandedCmExtensions = useMemo(
    () => [json(), jsonDarkTheme, jsonSyntaxHighlight, EditorView.editable.of(false), expandedJsonTypography],
    [],
  )

  const cmBasicSetup = {
    lineNumbers: true,
    foldGutter: true,
    highlightActiveLine: false,
    highlightActiveLineGutter: false,
  }

  const actions = displayText ? (
    <>
      <IconButton label="Copy JSON" title={copied ? 'Copied!' : 'Copy'} onClick={handleCopy}>
        {copied ? <Check className="h-icon-sm w-icon-sm text-emerald-300" /> : <Copy className="h-icon-sm w-icon-sm" />}
      </IconButton>
      <IconButton label="Expand JSON" title="Expand JSON" onClick={() => setExpanded(true)}>
        <Maximize2 className="h-icon-sm w-icon-sm" />
      </IconButton>
    </>
  ) : null

  return (
    <>
      <CodePanel
        title={<span className={compact ? undefined : 'text-system-control'}>Structured response</span>}
        icon={<Braces className="h-icon w-icon" />}
        badge={<span className={compact ? undefined : 'text-system-nano'}>JSON</span>}
        actions={actions}
        density={compact ? 'compact' : 'default'}
        className={className}
      >
        {displayText ? (
          <div
            className={cn('scrollbar-thin overflow-auto bg-background/20', compact && 'text-system-control')}
            style={{ maxHeight: typeof resolvedMaxHeight === 'number' ? `${resolvedMaxHeight}px` : resolvedMaxHeight }}
          >
            <CodeMirror
              value={displayText}
              extensions={inlineCmExtensions}
              readOnly
              basicSetup={cmBasicSetup}
              className="cm-custom-scroll"
              theme="none"
            />
          </div>
        ) : (
          <div className="p-ui-md">
            <EmptyStatePanel compact title="No structured output" description="This Run did not persist a structured response payload." />
          </div>
        )}
      </CodePanel>

      {expanded && (
        <div
          ref={overlayRef}
          className="fixed inset-0 z-focus flex items-center justify-center bg-background/82 p-ui-lg backdrop-blur-[2px]"
          onClick={(event) => { if (event.target === overlayRef.current) setExpanded(false) }}
        >
          <div role="dialog" aria-modal="true" aria-label="Structured response JSON" className="flex h-focus-workspace w-focus-workspace flex-col overflow-hidden rounded-container border border-border bg-surface shadow-overlay">
            <div className="flex min-h-panel-header shrink-0 items-center justify-between border-b border-border px-ui-md">
              <div className="flex min-w-0 items-center gap-ui-sm">
                <Braces className="h-icon w-icon shrink-0 text-primary-light" />
                <span className="truncate font-mono text-code-default font-semibold text-slate-50">Structured response</span>
                <span className="rounded-technical border border-primary/25 bg-primary/[0.08] px-ui-xs py-ui-hairline font-mono text-system-nano uppercase tracking-[0.08em] text-primary-light">JSON</span>
              </div>
              <div className="flex items-center gap-ui-xs">
                <IconButton label="Copy JSON" title={copied ? 'Copied!' : 'Copy'} onClick={handleCopy}>
                  {copied ? <Check className="h-icon-sm w-icon-sm text-emerald-300" /> : <Copy className="h-icon-sm w-icon-sm" />}
                </IconButton>
                <IconButton label="Close" title="Close" onClick={() => setExpanded(false)}>
                  <X className="h-icon-sm w-icon-sm" />
                </IconButton>
              </div>
            </div>
            <div className="min-h-0 flex-1 bg-background/20">
              <CodeMirror
                value={displayText}
                extensions={expandedCmExtensions}
                readOnly
                basicSetup={cmBasicSetup}
                theme="none"
                height="100%"
              />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
