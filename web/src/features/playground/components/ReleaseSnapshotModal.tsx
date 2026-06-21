import { FileText, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import type { AgentRelease } from '@/features/agents/types'

type ReleaseSnapshotModalProps = {
  open: boolean
  title: string
  description?: string
  release: AgentRelease | null
  confirmLabel?: string
  isConfirming?: boolean
  onConfirm?: () => void
  onClose: () => void
}

function formatJson(value: unknown) {
  if (!value) return '—'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function row(label: string, value: unknown) {
  return <div className="grid grid-cols-[96px_1fr] gap-3 text-xs"><span className="text-muted">{label}</span><span className="min-w-0 break-words text-slate-200">{value || '—'}</span></div>
}

export function ReleaseSnapshotModal({ open, title, description, release, confirmLabel, isConfirming, onConfirm, onClose }: ReleaseSnapshotModalProps) {
  if (!open || !release) return null

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
    <div className="max-h-[86vh] w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl">
      <div className="flex items-start justify-between gap-4 border-b border-border p-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2"><h2 className="text-base font-semibold text-white">{title}</h2><Badge variant="secondary">{release.version}</Badge></div>
          {description && <p className="text-xs text-muted">{description}</p>}
        </div>
        <button className="rounded-lg p-1 text-muted hover:text-white" onClick={onClose}><X className="h-4 w-4" /></button>
      </div>

      <div className="max-h-[60vh] space-y-5 overflow-y-auto p-5">
        <section className="space-y-2 rounded-xl border border-border bg-background/40 p-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-300"><FileText className="h-3.5 w-3.5" />Agent snapshot</div>
          {row('Name', release.name)}
          {row('Model', `${release.provider ?? '—'}/${release.model ?? '—'}`)}
          {row('Status', release.agent_status)}
          {row('Session', release.session_mode)}
          {row('Temp', release.temperature)}
          {row('Max tokens', release.max_output_tokens)}
        </section>

        <section className="space-y-2 rounded-xl border border-border bg-background/40 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">System prompt</p>
          <pre className="max-h-44 overflow-auto whitespace-pre-wrap rounded-lg bg-black/20 p-3 text-xs text-slate-200">{release.system_prompt || '—'}</pre>
        </section>

        <section className="space-y-2 rounded-xl border border-border bg-background/40 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Output / schema</p>
          <pre className="max-h-44 overflow-auto whitespace-pre-wrap rounded-lg bg-black/20 p-3 text-xs text-slate-200">{formatJson(release.output_schema ?? release.response_format)}</pre>
        </section>

        <section className="space-y-2 rounded-xl border border-border bg-background/40 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Runtime / knowledge</p>
          {row('Collections', release.collection_ids?.length ? `${release.collection_ids.length}` : '—')}
          <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-black/20 p-3 text-xs text-slate-200">{formatJson(release.runtime_config)}</pre>
        </section>
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-border p-4">
        <Button size="sm" variant="outline" onClick={onClose}>Close</Button>
        {onConfirm && confirmLabel && <Button size="sm" onClick={onConfirm} loading={isConfirming}>{confirmLabel}</Button>}
      </div>
    </div>
  </div>
}
