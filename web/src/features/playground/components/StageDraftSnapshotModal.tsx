import { AlertTriangle, FileText, Package } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import type { AgentRelease } from '@/features/agents/types'
import type { AgentEditorState } from '../AgentEditorContext'

type StageDraftSnapshotModalProps = {
  open: boolean
  state: AgentEditorState
  snapshot: Record<string, unknown>
  currentStaging: AgentRelease | null
  isConfirming?: boolean
  onClose: () => void
  onConfirm: () => void
}

function formatJson(value: unknown) {
  if (!value) return '—'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return formatJson(value)
}

function row(label: string, value: unknown) {
  return (
    <div className="grid grid-cols-[90px_1fr] gap-3 text-xs">
      <span className="text-muted">{label}</span>
      <span className="min-w-0 break-words text-slate-200">{formatValue(value)}</span>
    </div>
  )
}

function modelLabel(state: AgentEditorState) {
  return `${state.provider || '—'}/${state.model || '—'}`
}

function responseFormatLabel(state: AgentEditorState) {
  if (!state.responseFormat?.enabled) return 'Text'
  return state.responseFormat.type === 'json' ? `JSON${state.responseFormat.strict ? ' strict' : ''}` : 'Text'
}

export function StageDraftSnapshotModal({ open, state, snapshot, currentStaging, isConfirming, onClose, onConfirm }: StageDraftSnapshotModalProps) {
  if (!open) return null
  const outputSchema = snapshot.output_schema ?? state.outputSchema ?? state.responseFormat?.schema

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
      <div className="flex max-h-[86vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40">
        <div className="flex items-start justify-between gap-4 border-b border-border/90 bg-background/20 p-5">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-white">Stage current draft?</h2>
              <Badge variant="secondary">Current draft</Badge>
            </div>
            <p className="text-xs leading-5 text-muted">Review the editor configuration that will become the staging snapshot.</p>
          </div>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-[300px_1fr] overflow-hidden">
          <aside className="border-r border-border/90 bg-background/25 p-5">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">
                <Package className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{state.name || 'Untitled agent'}</p>
                <p className="text-[11px] text-muted">Draft to staging</p>
              </div>
            </div>

            {currentStaging && (
              <div className="mt-4 flex gap-2 rounded-xl border border-yellow-500/30 bg-yellow-500/[0.06] p-3 text-xs leading-5 text-yellow-100">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-yellow-400" />
                <p>This will replace the current staging snapshot: {currentStaging.version}.</p>
              </div>
            )}

            <section className="mt-4 space-y-2 rounded-xl border border-border/80 bg-background/45 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-300">
                <FileText className="h-3.5 w-3.5" />
                Snapshot
              </div>
              {row('Name', state.name || 'Untitled agent')}
              {row('Model', modelLabel(state))}
              {row('Session', state.sessionMode)}
              {row('Temp', state.temperature)}
              {row('Tokens', state.maxOutputTokens)}
              {row('Response', responseFormatLabel(state))}
              {row('Collections', state.collectionIds?.length ? `${state.collectionIds.length}` : '—')}
            </section>
          </aside>

          <div className="min-h-0 space-y-5 overflow-y-auto p-5">
            <section className="space-y-2 rounded-xl border border-border/80 bg-background/45 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">System prompt</p>
              <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border border-border/60 bg-black/20 p-3 text-xs text-slate-200">{state.systemPrompt || '—'}</pre>
            </section>

            <section className="space-y-2 rounded-xl border border-border/80 bg-background/45 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Output / schema</p>
              <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border border-border/60 bg-black/20 p-3 text-xs text-slate-200">{formatJson(outputSchema ?? snapshot.response_format)}</pre>
            </section>

            <section className="space-y-2 rounded-xl border border-border/80 bg-background/45 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Runtime config / knowledge</p>
              <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border border-border/60 bg-black/20 p-3 text-xs text-slate-200">{formatJson(snapshot.runtime_config ?? state.runtimeConfig)}</pre>
            </section>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border/90 bg-background/20 p-4">
          <Button size="sm" variant="outline" onClick={onClose} disabled={isConfirming}>Cancel</Button>
          <Button size="sm" onClick={onConfirm} loading={isConfirming}>Stage draft</Button>
        </div>
      </div>
    </div>
  )
}
