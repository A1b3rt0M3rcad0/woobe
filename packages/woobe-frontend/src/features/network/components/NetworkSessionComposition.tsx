import { Bot, CircleDashed, History, MessagesSquare } from 'lucide-react'
import { Badge, EmptyStatePanel, TechnicalListItem } from '@woobe/ui'

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
      <EmptyStatePanel
        compact
        icon={<CircleDashed className="h-icon-lg w-icon-lg" />}
        title="No Agent contexts yet"
        description="Agent contexts are created lazily when nodes execute."
      />
    )
  }

  return (
    <div className="space-y-ui-sm">
      {contexts.map((context) => (
        <TechnicalListItem
          key={context.id}
          leading={<Bot className="h-icon w-icon text-primary-light" />}
          label={context.agentName}
          description={contextLabel(context)}
          meta={(
            <span className="flex flex-wrap items-center gap-x-ui-md gap-y-ui-xs">
              {!compact ? <span className="inline-flex items-center gap-ui-xs"><History className="h-icon-sm w-icon-sm" />{context.invocationCount} invocations</span> : null}
              {!compact ? <span className="inline-flex items-center gap-ui-xs"><MessagesSquare className="h-icon-sm w-icon-sm" />{context.messageCount} messages</span> : null}
              <span>{context.version}</span>
              {context.agentSessionId ? <span className="text-primary-light">session {context.agentSessionId}</span> : null}
            </span>
          )}
          trailing={<Badge size="compact" variant={context.sessionMode === 'stateless' ? 'outline' : 'default'}>{context.sessionMode}</Badge>}
        />
      ))}
    </div>
  )
}
