import { AlertTriangle, Bot, KeyRound, Network, RotateCcw } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import type { ApiKey, RuntimeTargetType } from '@/features/api-keys/types'

interface RotateApiKeyDialogProps {
  open: boolean
  apiKey: ApiKey | null
  targetName?: string | null
  agentName?: string | null
  loading: boolean
  onClose: () => void
  onConfirm: () => void
}

function permissionLabel(scope: string): string {
  if (scope === 'traces:read') return 'Traces'
  if (scope === 'usage:read') return 'Usage & cost'
  if (scope === 'runtime:execute') return 'Runtime execution'
  return scope
}

function runtimeTargetType(apiKey: ApiKey): RuntimeTargetType {
  return apiKey.target_type === 'network' ? 'network' : 'agent'
}

export function RotateApiKeyDialog({
  open,
  apiKey,
  targetName,
  agentName,
  loading,
  onClose,
  onConfirm,
}: RotateApiKeyDialogProps) {
  const handleClose = () => {
    if (!loading) onClose()
  }

  const targetType = apiKey ? runtimeTargetType(apiKey) : 'agent'
  const targetLabel = targetType === 'network' ? 'Network' : 'Agent'
  const TargetIcon = targetType === 'network' ? Network : Bot
  const resolvedTargetName = targetName || agentName || apiKey?.target_id || apiKey?.agent_id || `${targetLabel} unavailable`

  return (
    <Dialog open={open} onClose={handleClose} title="Rotate API key" className="max-w-2xl" layer="nestedModal">
      {apiKey && (
        <div className="space-y-5">
          <section className="rounded-xl border border-border/80 bg-surface/60 p-4">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
                <RotateCcw className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{apiKey.name}</p>
                <code className="mt-1 block truncate text-xs text-muted">{apiKey.key_prefix}...</code>
              </div>
            </div>

            {apiKey.kind === 'runtime' ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-border/70 bg-background/55 p-3">
                  <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted"><TargetIcon className="h-3.5 w-3.5" />{targetLabel}</div>
                  <p className="mt-1 truncate text-sm font-medium text-white">{resolvedTargetName}</p>
                </div>
                <div className="rounded-lg border border-border/70 bg-background/55 p-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Environment</p>
                  <p className="mt-1 text-sm font-medium capitalize text-white">{apiKey.environment}</p>
                </div>
                <div className="rounded-lg border border-border/70 bg-background/55 p-3 sm:col-span-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Interfaces</p>
                  <p className="mt-1 text-sm text-white">{apiKey.interfaces.join(' · ')}</p>
                </div>
              </div>
            ) : (
              <div className="mt-4 rounded-lg border border-border/70 bg-background/55 p-3">
                <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted"><KeyRound className="h-3.5 w-3.5" />Permissions</div>
                <p className="mt-1 text-sm text-white">{apiKey.scopes.map(permissionLabel).join(' · ')}</p>
              </div>
            )}
          </section>

          <section className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
              <div>
                <p className="text-sm font-semibold text-amber-100">The current key stops working immediately</p>
                <p className="mt-1 text-xs leading-5 text-amber-100/70">Name, purpose, {targetLabel} binding, environment and interfaces remain unchanged. Only the secret changes.</p>
              </div>
            </div>
          </section>

          <p className="text-xs leading-5 text-muted">The replacement secret is shown only once after rotation. Copy it before closing the next dialog.</p>

          <div className="flex justify-end gap-2 border-t border-border/80 pt-4">
            <Button type="button" variant="outline" onClick={handleClose} disabled={loading}>Cancel</Button>
            <Button type="button" onClick={onConfirm} loading={loading}>Rotate key</Button>
          </div>
        </div>
      )}
    </Dialog>
  )
}
