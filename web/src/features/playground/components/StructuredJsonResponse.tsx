import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { json } from '@codemirror/lang-json'
import { EditorView } from '@codemirror/view'
import { Copy, Check, Maximize2, X, Braces } from 'lucide-react'
import { cn } from '@/lib/utils'
import { jsonDarkTheme, jsonSyntaxHighlight } from '@/components/ui/json-cm-theme'

interface StructuredJsonResponseProps {
  value: unknown
  raw?: string
  maxHeight?: number | string
  className?: string
}

export function StructuredJsonResponse({
  value,
  maxHeight = 420,
  className,
}: StructuredJsonResponseProps) {
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)

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
    navigator.clipboard.writeText(displayText)
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

  return (
    <>
      <div
        className={cn(
          'rounded-xl border overflow-hidden',
          'border-[rgba(148,163,184,0.22)]',
          'bg-[#0f172a]',
          className,
        )}
      >
        {/* Header */}
        <div
          className={cn(
            'flex items-center justify-between gap-2 px-4',
            'h-14',
            'bg-[rgba(30,41,59,0.45)]',
            'border-b border-[rgba(148,163,184,0.1)]',
          )}
        >
          <div className="flex items-center gap-2.5 min-w-0 flex-1">
            <Braces className="h-4 w-4 shrink-0 text-[#818cf8]" />
            <span className="text-sm font-medium text-[rgba(226,232,240,0.92)] truncate">
              Structured response
            </span>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {/* JSON Badge */}
            <span
              className={cn(
                'text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded',
                'bg-[rgba(99,102,241,0.12)] text-[#a5b4fc]',
              )}
            >
              JSON
            </span>

            {/* Copy */}
            {displayText && (
              <button
                onClick={handleCopy}
                className={cn(
                  'p-1.5 rounded-md transition-colors',
                  'text-[rgba(148,163,184,0.88)] hover:text-white',
                  'hover:bg-[rgba(255,255,255,0.05)]',
                  'border border-[rgba(148,163,184,0.18)]',
                )}
                title={copied ? 'Copied!' : 'Copy'}
                aria-label="Copy JSON"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            )}

            {/* Expand fullscreen */}
            {displayText && (
              <button
                onClick={handleExpand}
                className={cn(
                  'p-1.5 rounded-md transition-colors',
                  'text-[rgba(148,163,184,0.88)] hover:text-white',
                  'hover:bg-[rgba(255,255,255,0.05)]',
                  'border border-[rgba(148,163,184,0.18)]',
                )}
                title="Expand JSON"
                aria-label="Expand JSON"
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Body */}
        {displayText && (
          <div
            className="overflow-auto scrollbar-thin"
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

        {!displayText && (
          <div className="px-4 py-6 text-center">
            <p className="text-xs text-[rgba(148,163,184,0.6)]">No data</p>
          </div>
        )}
      </div>

      {/* Fullscreen overlay */}
      {expanded && (
        <div
          ref={overlayRef}
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#020617]/72 backdrop-blur-sm"
          onClick={(e) => { if (e.target === overlayRef.current) handleCloseExpand() }}
        >
          <div className="relative flex flex-col w-[95vw] max-w-[1600px] h-[90vh] rounded-xl border border-[rgba(148,163,184,0.22)] bg-[#0f172a] shadow-2xl">
            <div className="flex items-center justify-between shrink-0 px-5 py-4 border-b border-[rgba(148,163,184,0.1)]">
              <span className="text-sm font-medium text-[rgba(226,232,240,0.92)]">
                Structured response
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={handleCopy}
                  className="p-1.5 rounded-md text-[rgba(148,163,184,0.88)] hover:text-white hover:bg-[rgba(255,255,255,0.05)] transition-colors border border-[rgba(148,163,184,0.18)]"
                  title={copied ? 'Copied!' : 'Copy'}
                  aria-label="Copy JSON"
                >
                  {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                </button>
                <button
                  onClick={handleCloseExpand}
                  className="p-1.5 rounded-md text-[rgba(148,163,184,0.88)] hover:text-white hover:bg-[rgba(255,255,255,0.05)] transition-colors border border-[rgba(148,163,184,0.18)]"
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
              />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
