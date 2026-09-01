import type { ReactNode } from 'react'
import { ContextInspector } from '@/features/traces/components/ContextInspector'
import { useAgentRunDetail } from '@/features/traces/hooks'
import { AgentResultViewer } from './AgentResultViewer'
import { TraceDiagnosticsPanel } from './TraceDiagnosticsPanel'

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
  const { data: run } = useAgentRunDetail({
    runId: runId ?? undefined,
    traceId: runId ? undefined : traceId ?? undefined,
  })

  return (
    <div>
      {runId || traceId ? (
        <TraceDiagnosticsPanel traceId={traceId} runId={runId} />
      ) : (
        <div className="border-b border-border px-4 py-3">
          <p className="text-xs font-medium text-white">Execution diagnostics</p>
          <p className="mt-1 text-[10px] text-muted">Execution diagnostics are unavailable until this Agent Run has a durable identity.</p>
        </div>
      )}

      {children ? <div className="space-y-4 px-4 py-4">{children}</div> : null}

      {showResult && (run?.answer || run?.parsed_output != null) ? (
        <div className="border-t border-border px-4 py-4">
          <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Result</p>
          <div className="mt-2">
            <AgentResultViewer
              value={run.answer}
              parsedOutput={run.parsed_output}
              title={resultTitle}
              subtitle={resultSubtitle || `${run.provider || '—'}/${run.model || '—'}`}
              compact
            />
          </div>
        </div>
      ) : null}

      <ContextInspector
        traceId={runId ? undefined : traceId ?? undefined}
        runId={runId ?? undefined}
        finalizing={finalizing}
      />
    </div>
  )
}
