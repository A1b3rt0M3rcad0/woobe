import { Bot, CircleDashed, History, MessagesSquare } from 'lucide-react'

import { cn } from '@/lib/utils'

import type { NetworkAgentContext } from './networkSessionTypes'

function contextLabel(context: NetworkAgentContext) {
  if (context.sessionMode === 'stateless') return 'Stateless · isolated invocations'
  if (context.invocationCount > 1) return 'Stateful context · reused'
  return 'Stateful context · created in this session'
}

export function NetworkSessionComposition({
  contexts,
  compact = false,
}: {
  contexts: NetworkAgentContext[]
  compact?: boolean
}) {
  if (!contexts.length) {
    return (
      <div className="rounded-lg border border-dashed border-border p-4 text-center">
        <CircleDashed className="mx-auto h-5 w-5 text-muted/50" />
        <p className="mt-2 text-[10px] text-muted">Agent contexts are created lazily when nodes execute.</p>
      </div>
    )
  }

  return (
    <div className="space-y-1.5">
      {contexts.map((context) => (
        <div key={context.id} className="rounded-lg border border-border/75 bg-background/45 p-2.5">
          <div className="flex items-start gap-2">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border bg-surface">
              <Bot className="h-3.5 w-3.5 text-primary-light" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <p className="truncate text-[11px] font-medium text-white">{context.agentName}</p>
                <span className={cn(
                  'rounded border px-1.5 py-0.5 text-[9px] font-medium',
                  context.sessionMode === 'stateless'
                    ? 'border-slate-500/30 bg-slate-500/10 text-slate-300'
                    : 'border-blue-500/25 bg-blue-500/10 text-blue-300',
                )}>
                  {context.sessionMode}
                </span>
              </div>
              <p className="mt-1 text-[10px] text-muted">{contextLabel(context)}</p>
              {!compact ? (
                <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[9px] text-muted">
                  <span className="inline-flex items-center gap-1"><History className="h-3 w-3" />{context.invocationCount} invocations</span>
                  <span className="inline-flex items-center gap-1"><MessagesSquare className="h-3 w-3" />{context.messageCount} messages</span>
                  <span>{context.version}</span>
                </div>
              ) : null}
              {context.agentSessionId ? <code className="mt-1.5 block truncate text-[9px] text-primary-light">session {context.agentSessionId}</code> : null}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
