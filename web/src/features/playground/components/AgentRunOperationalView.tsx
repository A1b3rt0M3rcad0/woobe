import type { ReactNode } from 'react'
import { ContextInspector } from '@/features/traces/components/ContextInspector'
import { TraceDiagnosticsPanel } from './TraceDiagnosticsPanel'

interface AgentRunOperationalViewProps {
  traceId?: string | null
  runId?: string | null
  finalizing?: boolean
  children?: ReactNode
}

export function AgentRunOperationalView({
  traceId,
  runId,
  finalizing = false,
  children,
}: AgentRunOperationalViewProps) {
  return (
    <div>
      {traceId ? (
        <TraceDiagnosticsPanel traceId={traceId} />
      ) : (
        <div className="border-b border-border px-4 py-3">
          <p className="text-xs font-medium text-white">Execution diagnostics</p>
          <p className="mt-1 text-[10px] text-muted">
            Execution diagnostics are unavailable until this Agent Run has a Trace.
          </p>
        </div>
      )}

      {children ? <div className="space-y-4 px-4 py-4">{children}</div> : null}

      <ContextInspector
        traceId={runId ? undefined : traceId ?? undefined}
        runId={runId ?? undefined}
        finalizing={finalizing}
      />
    </div>
  )
}
