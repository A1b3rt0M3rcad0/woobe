import { Brain, ChevronRight, RefreshCw } from 'lucide-react'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { formatTokens } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'
import { useTraceModelInvocations } from '../hooks'
import type { ContextModelInvocation } from '../types'

function pressureClass(status: string | undefined): string {
  switch ((status ?? '').toUpperCase()) {
    case 'CRITICAL':
      return 'border-red-500/25 bg-red-500/10 text-red-400'
    case 'HIGH':
      return 'border-orange-500/25 bg-orange-500/10 text-orange-400'
    case 'MODERATE':
      return 'border-yellow-500/25 bg-yellow-500/10 text-yellow-400'
    case 'LOW':
      return 'border-emerald-500/25 bg-emerald-500/10 text-emerald-400'
    default:
      return 'border-border bg-background text-muted'
  }
}

function formatPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(value >= 0.1 ? 1 : 2)}%`
}

function formatUnits(value: number | null | undefined): string {
  return value == null ? '—' : formatTokens(value)
}

function SourceSummary({ invocation }: { invocation: ContextModelInvocation }) {
  const snapshot = invocation.context_snapshot
  if (!snapshot) return null

  const sources = snapshot.manifest?.sources
  if (!sources || typeof sources !== 'object' || Array.isArray(sources)) return null

  return (
    <div className="flex flex-wrap gap-1">
      {Object.entries(sources).map(([name, raw]) => {
        const value = raw && typeof raw === 'object' && !Array.isArray(raw)
          ? raw as Record<string, unknown>
          : {}
        const count = typeof value.count === 'number' ? value.count : null
        const units = typeof value.units === 'number' ? value.units : null
        return (
          <span
            key={name}
            className="rounded border border-border bg-background px-1.5 py-0.5 text-[10px] text-muted"
          >
            {name}{count != null ? ` · ${count}` : ''}{units != null ? ` · ${formatTokens(units)}` : ''}
          </span>
        )
      })}
    </div>
  )
}

function InvocationCard({ invocation }: { invocation: ContextModelInvocation }) {
  const snapshot = invocation.context_snapshot
  if (!snapshot) return null

  const reported = snapshot.reported_input_units
  const measured = reported ?? snapshot.estimated_input_units

  return (
    <div className="rounded-lg border border-border bg-background p-2.5 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-white truncate">
            Invocation #{invocation.call_index ?? '—'} · {invocation.phase || 'model_invocation'}
          </p>
          <p className="text-[10px] text-muted font-mono truncate">
            {invocation.provider || '—'}/{invocation.model || '—'}
          </p>
        </div>
        <span className={cn(
          'shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-medium',
          pressureClass(snapshot.pressure_status),
        )}>
          {snapshot.pressure_status || 'UNKNOWN'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        <div className="rounded border border-border px-2 py-1.5">
          <p className="text-[9px] uppercase tracking-wider text-muted">Input</p>
          <p className="text-[11px] font-mono text-white">{formatUnits(measured)}</p>
          <p className="text-[9px] text-muted">{snapshot.measurement_status}</p>
        </div>
        <div className="rounded border border-border px-2 py-1.5">
          <p className="text-[9px] uppercase tracking-wider text-muted">Usable budget</p>
          <p className="text-[11px] font-mono text-white">{formatUnits(snapshot.usable_input_budget)}</p>
          <p className="text-[9px] text-muted">{formatPercent(snapshot.utilization)} used</p>
        </div>
      </div>

      <SourceSummary invocation={invocation} />

      <div className="text-[10px] text-muted flex flex-wrap gap-x-3 gap-y-0.5">
        <span>Estimated {formatUnits(snapshot.estimated_input_units)}</span>
        <span>Reported {formatUnits(snapshot.reported_input_units)}</span>
        <span>Capacity {formatUnits(snapshot.model_capacity_units)}</span>
        <span>Output reserve {formatUnits(snapshot.reserved_output_units)}</span>
      </div>

      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-1 text-[10px] text-muted hover:text-white">
          <ChevronRight className="h-3 w-3 transition-transform group-open:rotate-90" />
          Context manifest
        </summary>
        <div className="mt-1.5 space-y-1.5">
          <JsonCodeBlock value={snapshot.manifest} maxHeight={160} />
          <JsonCodeBlock value={snapshot.contributions} maxHeight={160} />
          <p className="text-[9px] text-muted break-all">
            policy {snapshot.policy_hash} · materialized {snapshot.materialized_hash}
          </p>
          <p className="text-[9px] text-muted">
            retention {snapshot.retention_mode} · reproduction {snapshot.reproduction_level}
          </p>
        </div>
      </details>
    </div>
  )
}

export function ContextInspector({ traceId }: { traceId: string }) {
  const { data, isLoading, isError, error, refetch } = useTraceModelInvocations(traceId)

  if (isLoading) {
    return (
      <div className="px-4 pb-4">
        <div className="rounded-lg border border-border bg-surface/30 p-3 flex items-center gap-2 text-xs text-muted">
          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
          Loading Context evidence...
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="px-4 pb-4">
        <div className="rounded-lg border border-border bg-surface/30 p-3 space-y-1.5">
          <div className="flex items-center gap-2 text-xs text-muted">
            <Brain className="h-3.5 w-3.5" />
            Context evidence unavailable
          </div>
          {error instanceof Error && <p className="text-[10px] text-muted">{error.message}</p>}
          <button onClick={() => refetch()} className="text-[10px] text-primary hover:underline">
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (!data?.length) return null

  return (
    <div className="px-4 pb-4 space-y-2">
      <div className="flex items-center gap-2 border-t border-border pt-3">
        <Brain className="h-3.5 w-3.5 text-muted" />
        <span className="text-xs font-medium text-white">Context</span>
        <span className="ml-auto text-[10px] text-muted">{data.length} model invocation{data.length === 1 ? '' : 's'}</span>
      </div>
      {data.map((invocation, index) => (
        <InvocationCard key={invocation.id ?? `${invocation.call_index ?? index}-${index}`} invocation={invocation} />
      ))}
    </div>
  )
}
