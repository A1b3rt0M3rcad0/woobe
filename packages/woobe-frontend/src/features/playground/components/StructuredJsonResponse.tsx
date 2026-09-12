import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { json } from '@codemirror/lang-json'
import { EditorView } from '@codemirror/view'
import { Braces, Check, Copy, Maximize2, X } from 'lucide-react'
import { CodePanel, EmptyStatePanel } from '@woobe/ui'

import { jsonDarkTheme, jsonSyntaxHighlight } from '@/components/ui/json-cm-theme'
import { cn } from '@/lib/utils'

interface StructuredJsonResponseProps {
  value: unknown
  raw?: string
  maxHeight?: number | string
  className?: string
  density?: 'comfortable' | 'compact'
}

function IconButton({
  label,
  title,
  onClick,
  children,
}: {
  label: string
  title: string
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-7 w-7 items-center justify-center rounded-control border border-border bg-control/35 text-muted-foreground transition-colors hover:border-primary/30 hover:bg-control hover:text-slate-50"
      title={title}
      aria-label={label}
    >
      {children}
    </button>
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
  const resolvedMaxHeight = maxHeight ?? (compact ? 220 : 340)

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

  const actions = displayText ? (
    <>
      <IconButton label="Copy JSON" title={copied ? 'Copied!' : 'Copy'} onClick={handleCopy}>
        {copied ? <Check className="h-3 w-3 text-emerald-300" /> : <Copy className="h-3 w-3" />}
      </IconButton>
      <IconButton label="Expand JSON" title="Expand JSON" onClick={() => setExpanded(true)}>
        <Maximize2 className="h-3 w-3" />
      </IconButton>
    </>
  ) : null

  return (
    <>
      <CodePanel
        title="Structured response"
        icon={<Braces className="h-3.5 w-3.5" />}
        badge="JSON"
        actions={actions}
        density={compact ? 'compact' : 'default'}
        className={className}
      >
        {displayText ? (
          <div
            className={cn('scrollbar-thin overflow-auto bg-background/20', compact && 'text-[10px]')}
            style={{ maxHeight: typeof resolvedMaxHeight === 'number' ? `${resolvedMaxHeight}px` : resolvedMaxHeight }}
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
        ) : (
          <div className="p-3">
            <EmptyStatePanel compact title="No structured output" description="This Run did not persist a structured response payload." />
          </div>
        )}
      </CodePanel>

      {expanded && (
        <div
          ref={overlayRef}
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/82 p-4 backdrop-blur-[2px]"
          onClick={(event) => { if (event.target === overlayRef.current) setExpanded(false) }}
        >
          <div role="dialog" aria-modal="true" aria-label="Structured response JSON" className="flex h-[min(88svh,900px)] w-[min(94vw,1500px)] flex-col overflow-hidden rounded-container border border-border bg-surface">
            <div className="flex min-h-[44px] shrink-0 items-center justify-between border-b border-border px-3">
              <div className="flex min-w-0 items-center gap-2">
                <Braces className="h-3.5 w-3.5 shrink-0 text-primary-light" />
                <span className="truncate font-mono text-[10px] font-semibold text-slate-50">Structured response</span>
                <span className="rounded-technical border border-primary/25 bg-primary/[0.08] px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-[0.08em] text-primary-light">JSON</span>
              </div>
              <div className="flex items-center gap-1">
                <IconButton label="Copy JSON" title={copied ? 'Copied!' : 'Copy'} onClick={handleCopy}>
                  {copied ? <Check className="h-3 w-3 text-emerald-300" /> : <Copy className="h-3 w-3" />}
                </IconButton>
                <IconButton label="Close" title="Close" onClick={() => setExpanded(false)}>
                  <X className="h-3 w-3" />
                </IconButton>
              </div>
            </div>
            <div className="min-h-0 flex-1 bg-background/20">
              <CodeMirror
                value={displayText}
                extensions={cmExtensions}
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
