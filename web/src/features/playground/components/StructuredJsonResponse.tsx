import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { json } from '@codemirror/lang-json'
import { EditorView } from '@codemirror/view'
import { Braces, Check, Copy, Maximize2, X } from 'lucide-react'

import { jsonDarkTheme, jsonSyntaxHighlight } from '@/components/ui/json-cm-theme'
import { cn } from '@/lib/utils'

interface StructuredJsonResponseProps {
  value: unknown
  raw?: string
  maxHeight?: number | string
  className?: string
  density?: 'comfortable' | 'compact'
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
  const resolvedMaxHeight = maxHeight ?? (compact ? 260 : 420)

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

  const handleExpand = useCallback(() => {
    setExpanded(true)
  }, [])

  const handleCloseExpand = useCallback(() => {
    setExpanded(false)
  }, [])

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

  return (
    <>
      <div
        className={cn(
          'overflow-hidden border border-[rgba(148,163,184,0.22)] bg-[#0f172a]',
          compact ? 'rounded-lg' : 'rounded-xl',
          className,
        )}
      >
        <div
          className={cn(
            'flex items-center justify-between gap-2 border-b border-[rgba(148,163,184,0.1)] bg-[rgba(30,41,59,0.45)]',
            compact ? 'h-10 px-3' : 'h-14 px-4',
          )}
        >
          <div className={cn('flex min-w-0 flex-1 items-center', compact ? 'gap-2' : 'gap-2.5')}>
            <Braces className={cn('shrink-0 text-[#818cf8]', compact ? 'h-3.5 w-3.5' : 'h-4 w-4')} />
            <span
              className={cn(
                'truncate font-medium text-[rgba(226,232,240,0.92)]',
                compact ? 'text-[10px]' : 'text-sm',
              )}
            >
              Structured response
            </span>
          </div>

          <div className={cn('flex shrink-0 items-center', compact ? 'gap-1' : 'gap-1.5')}>
            <span
              className={cn(
                'rounded bg-[rgba(99,102,241,0.12)] font-semibold uppercase tracking-wider text-[#a5b4fc]',
                compact ? 'px-1.5 py-0.5 text-[8px]' : 'px-1.5 py-0.5 text-[10px]',
              )}
            >
              JSON
            </span>

            {displayText && (
              <button
                type="button"
                onClick={handleCopy}
                className={cn(
                  'rounded-md border border-[rgba(148,163,184,0.18)] text-[rgba(148,163,184,0.88)] transition-colors hover:bg-[rgba(255,255,255,0.05)] hover:text-white',
                  compact ? 'p-1' : 'p-1.5',
                )}
                title={copied ? 'Copied!' : 'Copy'}
                aria-label="Copy JSON"
              >
                {copied ? (
                  <Check className={cn('text-emerald-400', compact ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
                ) : (
                  <Copy className={compact ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
                )}
              </button>
            )}

            {displayText && (
              <button
                type="button"
                onClick={handleExpand}
                className={cn(
                  'rounded-md border border-[rgba(148,163,184,0.18)] text-[rgba(148,163,184,0.88)] transition-colors hover:bg-[rgba(255,255,255,0.05)] hover:text-white',
                  compact ? 'p-1' : 'p-1.5',
                )}
                title="Expand JSON"
                aria-label="Expand JSON"
              >
                <Maximize2 className={compact ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
              </button>
            )}
          </div>
        </div>

        {displayText && (
          <div
            className={cn('scrollbar-thin overflow-auto', compact && 'text-[10px]')}
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
        )}

        {!displayText && (
          <div className={compact ? 'px-3 py-4 text-center' : 'px-4 py-6 text-center'}>
            <p className={cn('text-[rgba(148,163,184,0.6)]', compact ? 'text-[9px]' : 'text-xs')}>No data</p>
          </div>
        )}
      </div>

      {expanded && (
        <div
          ref={overlayRef}
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#020617]/72 backdrop-blur-sm"
          onClick={(event) => { if (event.target === overlayRef.current) handleCloseExpand() }}
        >
          <div className="relative flex h-[90vh] w-[95vw] max-w-[1600px] flex-col rounded-xl border border-[rgba(148,163,184,0.22)] bg-[#0f172a] shadow-2xl">
            <div className="flex shrink-0 items-center justify-between border-b border-[rgba(148,163,184,0.1)] px-5 py-4">
              <span className="text-sm font-medium text-[rgba(226,232,240,0.92)]">Structured response</span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={handleCopy}
                  className="rounded-md border border-[rgba(148,163,184,0.18)] p-1.5 text-[rgba(148,163,184,0.88)] transition-colors hover:bg-[rgba(255,255,255,0.05)] hover:text-white"
                  title={copied ? 'Copied!' : 'Copy'}
                  aria-label="Copy JSON"
                >
                  {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                </button>
                <button
                  type="button"
                  onClick={handleCloseExpand}
                  className="rounded-md border border-[rgba(148,163,184,0.18)] p-1.5 text-[rgba(148,163,184,0.88)] transition-colors hover:bg-[rgba(255,255,255,0.05)] hover:text-white"
                  aria-label="Close"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="min-h-0 flex-1">
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
