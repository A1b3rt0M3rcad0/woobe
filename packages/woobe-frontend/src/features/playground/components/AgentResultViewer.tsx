import { useState } from 'react'
import { Check, Copy, FileText } from 'lucide-react'

import { Dialog } from '@/components/ui/Dialog'
import { cn } from '@/lib/utils'

import { MarkdownMessage } from './MarkdownMessage'
import { StructuredJsonResponse } from './StructuredJsonResponse'

interface AgentResultViewerProps {
  value?: string | null
  parsedOutput?: unknown | null
  title?: string
  subtitle?: string
  compact?: boolean
  emptyLabel?: string
}

type TextView = 'rendered' | 'raw'

export function AgentResultViewer({
  value,
  parsedOutput,
  title = 'Agent result',
  subtitle,
  compact = false,
  emptyLabel = 'No output was produced.',
}: AgentResultViewerProps) {
  const [open, setOpen] = useState(false)
  const [view, setView] = useState<TextView>('rendered')
  const [copied, setCopied] = useState(false)

  if (parsedOutput != null) {
    return <StructuredJsonResponse value={parsedOutput} density={compact ? 'compact' : 'comfortable'} />
  }

  const text = value?.trim() ? value : null
  if (!text) return <p className={compact ? 'text-[10px] text-muted' : 'text-xs text-muted'}>{emptyLabel}</p>

  const copy = async () => {
    await navigator.clipboard?.writeText(text)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }

  return (
    <>
      <div>
        <div className={cn('line-clamp-4 overflow-hidden text-slate-200', compact ? 'text-[10px] leading-5' : 'text-xs leading-5')}>
          <MarkdownMessage content={text} className={compact ? 'space-y-1.5 text-[10px] leading-5' : 'space-y-2'} />
        </div>
        <button type="button" onClick={() => setOpen(true)} className={cn('mt-2 font-medium text-primary-light hover:text-white', compact ? 'text-[9px]' : 'text-[11px]')}>
          View full result
        </button>
      </div>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={title}
        scrollMode="content"
        className="max-w-5xl"
        contentClassName="p-0"
      >
        <div className="flex min-h-[60vh] flex-col">
          <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-xs text-white"><FileText className="h-3.5 w-3.5 text-primary-light" />Markdown result</div>
              {subtitle ? <p className="mt-0.5 truncate text-[10px] text-muted">{subtitle}</p> : null}
            </div>
            <div className="flex items-center gap-2">
              <div className="flex rounded-lg border border-border bg-background/50 p-1">
                {(['rendered', 'raw'] as const).map((target) => (
                  <button
                    key={target}
                    type="button"
                    onClick={() => setView(target)}
                    className={cn('rounded-md px-3 py-1.5 text-[10px] font-medium capitalize', view === target ? 'bg-primary/10 text-primary-light' : 'text-muted hover:text-white')}
                  >
                    {target}
                  </button>
                ))}
              </div>
              <button type="button" onClick={() => void copy()} className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-[10px] text-muted hover:text-white" title={copied ? 'Copied' : 'Copy result'}>
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-6 scrollbar-thin">
            {view === 'rendered' ? (
              <div className="mx-auto max-w-4xl rounded-xl border border-border/80 bg-background/35 px-6 py-5 text-sm leading-relaxed text-white">
                <MarkdownMessage content={text} />
              </div>
            ) : (
              <pre className="mx-auto max-w-4xl whitespace-pre-wrap break-words rounded-xl border border-border/80 bg-background/70 p-5 font-mono text-xs leading-5 text-slate-200">{text}</pre>
            )}
          </div>
        </div>
      </Dialog>
    </>
  )
}
