import { useState } from 'react'
import { Check, Copy, FileText } from 'lucide-react'
import { CodePanel, EmptyStatePanel } from '@woobe/ui'

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
  if (!text) return <EmptyStatePanel compact title={emptyLabel} />

  const copy = async () => {
    await navigator.clipboard?.writeText(text)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }

  return (
    <>
      <div>
        <div className={cn('line-clamp-4 overflow-hidden font-sans text-slate-200', compact ? 'text-[10px] leading-5' : 'text-[12px] leading-5')}>
          <MarkdownMessage content={text} className={compact ? 'space-y-1.5 text-[10px] leading-5' : 'space-y-2'} />
        </div>
        <button type="button" onClick={() => setOpen(true)} className={cn('mt-2 font-mono text-primary-light hover:text-white', compact ? 'text-[8px]' : 'text-[9px]')}>
          View full result
        </button>
      </div>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={title}
        variant="workspace"
        height="workspace"
        contentClassName="min-h-0 flex-1 p-0"
      >
        <div className="flex h-full min-h-0 flex-col">
          <div className="flex min-h-[46px] shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-2.5">
            <div className="min-w-0">
              <div className="flex items-center gap-2 font-mono text-[9px] font-semibold text-slate-100"><FileText className="h-3.5 w-3.5 text-primary-light" />Markdown result</div>
              {subtitle ? <p className="mt-0.5 truncate font-mono text-[8px] text-muted-foreground">{subtitle}</p> : null}
            </div>
            <div className="flex items-center gap-1.5">
              <div className="flex rounded-control border border-border bg-background/35 p-[2px]">
                {(['rendered', 'raw'] as const).map((target) => (
                  <button
                    key={target}
                    type="button"
                    onClick={() => setView(target)}
                    className={cn('h-[25px] rounded-technical px-2.5 font-mono text-[8px] capitalize transition-colors', view === target ? 'bg-primary/[0.10] text-primary-light' : 'text-muted-foreground hover:bg-control hover:text-slate-50')}
                  >
                    {target}
                  </button>
                ))}
              </div>
              <button type="button" onClick={() => void copy()} className="inline-flex h-[29px] items-center gap-1 rounded-control border border-border bg-control/30 px-2 font-mono text-[8px] text-muted-foreground hover:bg-control hover:text-slate-50" title={copied ? 'Copied' : 'Copy result'}>
                {copied ? <Check className="h-3 w-3 text-emerald-300" /> : <Copy className="h-3 w-3" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
          </div>

          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto bg-background/15 p-4">
            {view === 'rendered' ? (
              <CodePanel title="Rendered response" icon={<FileText className="h-3.5 w-3.5" />}>
                <div className="p-4 font-sans text-[12px] leading-6 text-slate-100">
                  <MarkdownMessage content={text} />
                </div>
              </CodePanel>
            ) : (
              <CodePanel title="Raw response" badge="TEXT">
                <pre className="scrollbar-thin max-h-[560px] overflow-auto whitespace-pre-wrap break-words p-4 font-mono text-[10px] leading-5 text-slate-200">{text}</pre>
              </CodePanel>
            )}
          </div>
        </div>
      </Dialog>
    </>
  )
}
