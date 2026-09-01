import { X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import type { AgentRelease } from '@/features/agents/types'

interface ConfirmVersionModalProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  versionName: string
  currentSnapshot: Record<string, unknown>
  lastRelease: AgentRelease | null
  hasUnsavedChanges: boolean
  isPending: boolean
}

const DIFF_FIELDS: { key: string; label: string }[] = [
  { key: 'name', label: 'Name' },
  { key: 'description', label: 'Description' },
  { key: 'system_prompt', label: 'System Prompt' },
  { key: 'provider', label: 'Provider' },
  { key: 'model', label: 'Model' },
  { key: 'temperature', label: 'Temperature' },
  { key: 'max_output_tokens', label: 'Max Tokens' },
  { key: 'session_mode', label: 'Session Mode' },
  { key: 'agent_status', label: 'Status' },
  { key: 'output_schema', label: 'Output Schema' },
  { key: 'collection_ids', label: 'Knowledge Collections' },
]

function formatValue(val: unknown): string {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'object') return JSON.stringify(val).slice(0, 80) + (JSON.stringify(val).length > 80 ? '...' : '')
  return String(val)
}

function changesExist(current: unknown, previous: unknown): boolean {
  return JSON.stringify(current) !== JSON.stringify(previous)
}

export function ConfirmVersionModal({ open, onClose, onConfirm, versionName, currentSnapshot, lastRelease, hasUnsavedChanges, isPending }: ConfirmVersionModalProps) {
  if (!open) return null

  const changedFields = DIFF_FIELDS.filter(({ key }) => {
    const current = currentSnapshot[key]
    const previous = lastRelease ? (lastRelease as unknown as Record<string, unknown>)[key] : undefined
    return changesExist(current, previous)
  })

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-full max-w-lg rounded-xl border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-sm font-semibold text-white">New Version</h2>
          <button onClick={onClose} className="p-1 rounded-md text-muted hover:text-white hover:bg-accent transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {hasUnsavedChanges && (
            <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-3">
              <p className="text-xs text-yellow-300 font-medium">Draft has unsaved changes</p>
              <p className="text-[11px] text-muted mt-1">These changes will be included in the version. Consider saving draft first.</p>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-muted mb-1">Version Name</label>
            <div className="rounded-lg border border-border bg-background p-2.5 text-xs font-mono text-muted">
              {versionName}
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-muted mb-2">Changes from previous version</p>
            {changedFields.length === 0 ? (
              <p className="text-xs text-muted italic">No changes detected — snapshot will be identical to the latest version.</p>
            ) : (
              <div className="rounded-lg border border-border overflow-hidden">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="border-b border-border bg-background/50">
                      <th className="text-left px-3 py-1.5 text-muted font-medium">Field</th>
                      <th className="text-left px-3 py-1.5 text-muted font-medium">Previous</th>
                      <th className="text-left px-3 py-1.5 text-muted font-medium">New</th>
                    </tr>
                  </thead>
                  <tbody>
                    {changedFields.map(({ key, label }) => {
                      const current = currentSnapshot[key]
                      const previous = lastRelease ? (lastRelease as unknown as Record<string, unknown>)[key] : undefined
                      return (
                        <tr key={key} className="border-b border-border/50 last:border-b-0">
                          <td className="px-3 py-1.5 text-muted font-medium">{label}</td>
                          <td className="px-3 py-1.5 text-muted max-w-[120px] truncate">{formatValue(previous)}</td>
                          <td className="px-3 py-1.5 text-white max-w-[120px] truncate">
                            <Badge variant="warning" className="text-[9px] mr-1">new</Badge>
                            {formatValue(current)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-border">
          <Button size="sm" variant="outline" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={onConfirm} loading={isPending}>
            Create Version
          </Button>
        </div>
      </div>
    </div>
  )
}
