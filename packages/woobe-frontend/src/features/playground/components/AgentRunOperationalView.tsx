import { useEffect, useRef, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { SectionBlock } from '@woobe/ui'
import { shouldRefreshContextEvidence, useAgentRunDetail } from '@/features/traces/hooks'
import { AgentResultViewer } from './AgentResultViewer'
import { AgentRunAnalyticsPanel } from './AgentRunAnalyticsPanel'

interface AgentRunOperationalViewProps {
  traceId?: string | null
  runId?: string | null
  finalizing?: boolean
  children?: ReactNode
  showResult?: boolean
  resultTitle?: string
  resultSubtitle?: string
}

export function AgentRunOperationalView({
  traceId,
  runId,
  finalizing = false,
  children,
  showResult = true,
  resultTitle = 'Agent result',
  resultSubtitle,
}: AgentRunOperationalViewProps) {
  const queryClient = useQueryClient()
  const { data: run } = useAgentRunDetail({
    runId: runId ?? undefined,
    traceId: runId ? undefined : traceId ?? undefined,
  })
  const previousStatus = useRef<string | undefined>(undefined)
  const identityKind = runId ? 'run' : traceId ? 'trace' : null
  const identityId = runId ?? traceId ?? null

  useEffect(() => {
    const currentStatus = run?.status
    if (identityKind && identityId && shouldRefreshContextEvidence(previousStatus.current, currentStatus)) {
      void queryClient.invalidateQueries({
        queryKey: ['context-evidence', { kind: identityKind, id: identityId }],
        exact: true,
      })
    }
    previousStatus.current = currentStatus
  }, [identityId, identityKind, queryClient, run?.status])

  return (
    <div>
      <AgentRunAnalyticsPanel traceId={traceId} runId={runId} finalizing={finalizing} />
      {children ? <div className="space-y-3 px-3 py-3">{children}</div> : null}
      {showResult && (run?.answer || run?.parsed_output != null) ? (
        <div className="border-t border-border px-3 py-3">
          <SectionBlock
            density="compact"
            eyebrow="Result"
            title={resultTitle}
            description={resultSubtitle || `${run.provider || '—'}/${run.model || '—'}`}
            className="bg-background/20"
          >
            <AgentResultViewer
              value={run.answer}
              parsedOutput={run.parsed_output}
              title={resultTitle}
              subtitle={resultSubtitle || `${run.provider || '—'}/${run.model || '—'}`}
              compact
            />
          </SectionBlock>
        </div>
      ) : null}
    </div>
  )
}
