import { Link } from 'react-router-dom'
import { CopyButton } from '@/components/common/CopyButton'
import { Badge } from '@/components/ui/Badge'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { Key, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useReleases } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import {
  buildApiReferenceForSlot,
  runtimeCurl,
  type RuntimeSlot,
} from '../lib/api-reference-contracts'

interface ApiModalProps {
  open: boolean
  onClose: () => void
  agent: Agent
  orgProjectPathFn: (projId: string, ...segments: string[]) => string
  projectId: string
}

const slotLabels: Record<RuntimeSlot, string> = {
  production: 'Production Release',
  staging: 'Staging Release',
}

export function ApiModal({ open, onClose, agent, orgProjectPathFn, projectId }: ApiModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const [activeSlot, setActiveSlot] = useState<RuntimeSlot>('production')
  const { data: releases = [] } = useReleases(agent.id)

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  const productionRelease = useMemo(
    () => releases.find((release) => release.status === 'production') ?? null,
    [releases],
  )
  const stagingRelease = useMemo(
    () => releases.find((release) => release.status === 'staging') ?? null,
    [releases],
  )

  const activeRelease = activeSlot === 'production' ? productionRelease : stagingRelease
  const reference = useMemo(
    () => buildApiReferenceForSlot({
      slot: activeSlot,
      release: activeRelease,
      projectId,
      agentId: agent.id,
    }),
    [activeSlot, activeRelease, projectId, agent.id],
  )

  const activeCurl = useMemo(
    () => runtimeCurl(projectId, agent.id, activeSlot),
    [projectId, agent.id, activeSlot],
  )
  const activeStreamCurl = useMemo(
    () => runtimeCurl(projectId, agent.id, activeSlot, true),
    [projectId, agent.id, activeSlot],
  )

  if (!open) return null

  const p = orgProjectPathFn

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-start justify-center pt-12 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <ScrollArea className="w-full max-w-3xl max-h-[84vh] rounded-xl border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-border sticky top-0 bg-surface z-10">
          <div>
            <h2 className="text-sm font-semibold text-white">API Reference</h2>
            <p className="mt-0.5 text-[11px] text-muted">Runtime contracts are generated from the active release snapshot for each slot.</p>
          </div>
          <button onClick={onClose} className="p-1 rounded-md text-muted hover:text-white hover:bg-accent transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-5">
          <div>
            <p className="text-xs font-medium text-muted mb-1">Agent ID</p>
            <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-3">
              <code className="text-sm flex-1 break-all">{agent.id}</code>
              <CopyButton text={agent.id} />
            </div>
          </div>

          <div className="rounded-lg border border-border bg-background p-3 text-xs text-muted space-y-2">
            <p><strong className="text-white">production</strong> uses the active production release snapshot.</p>
            <p><strong className="text-white">staging</strong> uses the active staging release snapshot.</p>
            <p><strong className="text-white">playground</strong> is reserved for editor draft execution and snapshot overrides; it is not the public runtime contract shown here.</p>
          </div>

          <div>
            <p className="text-xs font-medium text-muted mb-2">Runtime Slot</p>
            <div className="grid grid-cols-2 gap-2">
              {(['production', 'staging'] as RuntimeSlot[]).map((slot) => {
                const release = slot === 'production' ? productionRelease : stagingRelease
                const active = activeSlot === slot
                return (
                  <button
                    key={slot}
                    type="button"
                    onClick={() => setActiveSlot(slot)}
                    className={`rounded-lg border p-3 text-left transition-colors ${
                      active ? 'border-primary bg-primary/10' : 'border-border bg-background hover:border-primary/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-white">{slotLabels[slot]}</span>
                      <Badge variant={release ? (slot === 'production' ? 'success' : 'warning') : 'secondary'} className="text-[10px]">
                        {release ? release.version : 'not deployed'}
                      </Badge>
                    </div>
                    <p className="mt-1 text-[11px] text-muted">
                      {release ? `${release.provider ?? 'provider'}/${release.model ?? 'model'}` : `No ${slot} release is available.`}
                    </p>
                  </button>
                )
              })}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-background p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold text-muted uppercase tracking-wider">Selected Slot Snapshot</p>
                <p className="mt-1 text-sm text-white">{slotLabels[activeSlot]}</p>
              </div>
              <Badge variant={reference.available ? (activeSlot === 'production' ? 'success' : 'warning') : 'secondary'}>
                {reference.release?.version ?? 'not deployed'}
              </Badge>
            </div>

            {reference.release ? (
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted">
                <p>Provider: <code className="text-white">{reference.release.provider}</code></p>
                <p>Model: <code className="text-white">{reference.release.model}</code></p>
                <p>Session mode: <code className="text-white">{reference.release.session_mode ?? 'default'}</code></p>
                <p>Structured output: <code className="text-white">{reference.release.structured_output_enabled ? 'enabled' : 'disabled'}</code></p>
                <p>Strict JSON: <code className="text-white">{reference.release.strict_json ? 'true' : 'false'}</code></p>
                <p>Fallback: <code className="text-white">{reference.release.fallback_model ? `${reference.release.fallback_provider}/${reference.release.fallback_model}` : 'none'}</code></p>
              </div>
            ) : null}

            {reference.warnings.length > 0 && (
              <div className="mt-3 rounded-md border border-yellow-500/30 bg-yellow-500/5 p-2 text-xs text-yellow-300 space-y-1">
                {reference.warnings.map((warning) => <p key={warning}>{warning}</p>)}
              </div>
            )}
          </div>

          <div>
            <p className="text-xs font-medium text-muted mb-1">Endpoints</p>
            <div className="space-y-1">
              <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
                <span className="text-xs font-medium text-primary">POST</span>
                <code className="text-xs flex-1">/runtime/ask</code>
                <CopyButton text="POST /runtime/ask" />
              </div>
              <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
                <span className="text-xs font-medium text-primary">POST</span>
                <code className="text-xs flex-1">/runtime/ask/stream</code>
                <CopyButton text="POST /runtime/ask/stream" />
              </div>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-muted mb-1">Request Contract</p>
            <JsonCodeBlock value={reference.request} maxHeight={360} actions={['copy', 'format']} />
          </div>

          <div>
            <p className="text-xs font-medium text-muted mb-1">cURL — {slotLabels[activeSlot]}</p>
            <ScrollArea orientation="horizontal" className="rounded-lg border border-border bg-background">
              <pre className="p-4 text-xs text-muted">{activeCurl}</pre>
            </ScrollArea>
            <CopyButton text={activeCurl} />
          </div>

          <div>
            <p className="text-xs font-medium text-muted mb-1">Sync Response Contract — POST /runtime/ask</p>
            <p className="text-[11px] text-muted mb-2">HTTP responses use the API envelope: <code>{'{ success, data }'}</code>.</p>
            <JsonCodeBlock value={reference.sync_response_contract} maxHeight={520} actions={['copy', 'format']} />
          </div>

          <div>
            <p className="text-xs font-medium text-muted mb-1">Sync Response Example — {slotLabels[activeSlot]}</p>
            <JsonCodeBlock value={reference.sync_response_example} maxHeight={520} actions={['copy', 'format']} />
          </div>

          <div>
            <p className="text-xs font-medium text-muted mb-1">Streaming cURL — {slotLabels[activeSlot]}</p>
            <ScrollArea orientation="horizontal" className="rounded-lg border border-border bg-background">
              <pre className="p-4 text-xs text-muted">{activeStreamCurl}</pre>
            </ScrollArea>
            <CopyButton text={activeStreamCurl} />
          </div>

          <div>
            <p className="text-xs font-medium text-muted mb-1">Streaming Response Contract — POST /runtime/ask/stream</p>
            <p className="text-[11px] text-muted mb-2">Streaming uses Server-Sent Events. The final <code>done</code> event carries the response object directly, without the <code>success/data</code> envelope.</p>
            <JsonCodeBlock value={reference.stream_events} maxHeight={620} actions={['copy', 'format']} />
          </div>

          <div>
            <div className="flex items-center gap-2 mb-1">
              <p className="text-xs font-medium text-muted">Structured Output — {slotLabels[activeSlot]}</p>
              <Badge variant={reference.structured_output.enabled ? 'success' : 'secondary'} className="text-[10px]">
                {reference.structured_output.enabled ? 'Enabled' : 'Disabled'}
              </Badge>
            </div>
            <p className="text-xs text-muted mb-2">
              Structured output is generated from the selected slot release snapshot, not from the draft agent settings.
            </p>
            <JsonCodeBlock value={reference.structured_output} maxHeight={520} actions={['copy', 'format']} />
          </div>

          <Link
            to={p(projectId, 'api-keys')}
            className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
          >
            <Key className="h-4 w-4" />
            Manage API Keys
          </Link>
        </div>
      </ScrollArea>
    </div>
  )
}
