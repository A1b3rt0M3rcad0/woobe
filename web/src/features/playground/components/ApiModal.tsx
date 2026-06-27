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
  const [activeSection, setActiveSection] = useState<'request' | 'sync' | 'stream' | 'structured'>('request')
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
  const sections = [
    { id: 'request' as const, label: 'Request' },
    { id: 'sync' as const, label: 'Sync' },
    { id: 'stream' as const, label: 'Streaming' },
    { id: 'structured' as const, label: 'Structured Output' },
  ]

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md"
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div className="flex h-[86vh] w-full max-w-[1180px] flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40">
        <div className="flex items-start justify-between gap-4 border-b border-border/90 bg-background/20 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-white">API Reference</h2>
            <p className="mt-0.5 text-[11px] text-muted">Runtime contracts generated from the active release snapshot.</p>
          </div>
          <button onClick={onClose} className="rounded-lg border border-transparent p-1 text-muted transition-colors hover:border-border/80 hover:bg-background/60 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-[320px_1fr]">
          <aside className="min-h-0 border-r border-border/90 bg-background/20 p-4">
            <div className="space-y-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Agent ID</p>
                <div className="mt-2 flex items-center gap-2 rounded-xl border border-border/80 bg-background/55 p-2.5">
                  <code className="min-w-0 flex-1 break-all text-[11px] text-white">{agent.id}</code>
                  <CopyButton text={agent.id} />
                </div>
              </div>

              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Runtime Slot</p>
                <div className="mt-2 space-y-2">
                  {(['production', 'staging'] as RuntimeSlot[]).map((slot) => {
                    const release = slot === 'production' ? productionRelease : stagingRelease
                    const active = activeSlot === slot
                    return (
                      <button
                        key={slot}
                        type="button"
                        onClick={() => setActiveSlot(slot)}
                        className={`w-full rounded-xl border p-3 text-left transition-colors ${
                          active ? 'border-primary/35 bg-primary/10 shadow-sm shadow-primary/5' : 'border-border/80 bg-background/45 hover:border-primary/30 hover:bg-background/70'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold text-white">{slotLabels[slot]}</span>
                          <Badge variant={release ? (slot === 'production' ? 'success' : 'warning') : 'secondary'} className="text-[10px]">
                            {release ? release.version : 'not deployed'}
                          </Badge>
                        </div>
                        <p className="mt-1 truncate text-[11px] text-muted">
                          {release ? `${release.provider ?? 'provider'}/${release.model ?? 'model'}` : `No ${slot} release is available.`}
                        </p>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="rounded-xl border border-border/80 bg-background/45 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Selected Snapshot</p>
                    <p className="mt-1 text-sm font-medium text-white">{slotLabels[activeSlot]}</p>
                  </div>
                  <Badge variant={reference.available ? (activeSlot === 'production' ? 'success' : 'warning') : 'secondary'}>
                    {reference.release?.version ?? 'not deployed'}
                  </Badge>
                </div>
                {reference.release ? (
                  <div className="mt-3 space-y-1 text-[11px] text-muted">
                    <p>Provider: <code className="text-white">{reference.release.provider}</code></p>
                    <p>Model: <code className="text-white">{reference.release.model}</code></p>
                    <p>Session: <code className="text-white">{reference.release.session_mode ?? 'default'}</code></p>
                    <p>Structured: <code className="text-white">{reference.release.structured_output_enabled ? 'enabled' : 'disabled'}</code></p>
                  </div>
                ) : null}
                {reference.warnings.length > 0 && (
                  <div className="mt-3 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-2 text-[11px] text-yellow-300">
                    {reference.warnings.map((warning) => <p key={warning}>{warning}</p>)}
                  </div>
                )}
              </div>

              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Endpoints</p>
                <div className="mt-2 space-y-1.5">
                  <div className="flex items-center gap-2 rounded-lg border border-border/80 bg-background/45 p-2">
                    <span className="text-[10px] font-semibold text-primary-light">POST</span>
                    <code className="min-w-0 flex-1 truncate text-[11px]">/runtime/ask</code>
                    <CopyButton text="POST /runtime/ask" />
                  </div>
                  <div className="flex items-center gap-2 rounded-lg border border-border/80 bg-background/45 p-2">
                    <span className="text-[10px] font-semibold text-primary-light">POST</span>
                    <code className="min-w-0 flex-1 truncate text-[11px]">/runtime/ask/stream</code>
                    <CopyButton text="POST /runtime/ask/stream" />
                  </div>
                </div>
              </div>

              <Link
                to={p(projectId, 'api-keys')}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border/80 bg-background/55 px-3 py-2 text-xs font-medium text-muted transition-colors hover:border-primary/30 hover:bg-primary/5 hover:text-white"
              >
                <Key className="h-4 w-4" />
                Manage API Keys
              </Link>
            </div>
          </aside>

          <section className="flex min-h-0 flex-col">
            <div className="flex gap-1 border-b border-border/90 bg-surface/70 p-1.5">
              {sections.map((section) => (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => setActiveSection(section.id)}
                  className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                    activeSection === section.id
                      ? 'border-primary/35 bg-primary/10 text-primary-light shadow-sm shadow-primary/5'
                      : 'border-transparent text-muted hover:border-border/80 hover:bg-background/60 hover:text-white'
                  }`}
                >
                  {section.label}
                </button>
              ))}
            </div>

            <ScrollArea className="min-h-0 flex-1">
              <div className="space-y-4 p-4">
                {activeSection === 'request' && (
                  <>
                    <div>
                      <p className="mb-1 text-xs font-medium text-muted">Request Contract</p>
                      <JsonCodeBlock value={reference.request} maxHeight={380} actions={['copy', 'format']} />
                    </div>
                    <div>
                      <p className="mb-1 text-xs font-medium text-muted">cURL — {slotLabels[activeSlot]}</p>
                      <ScrollArea orientation="horizontal" className="rounded-xl border border-border/80 bg-background/60">
                        <pre className="p-4 text-xs text-muted">{activeCurl}</pre>
                      </ScrollArea>
                      <div className="mt-2"><CopyButton text={activeCurl} /></div>
                    </div>
                  </>
                )}

                {activeSection === 'sync' && (
                  <>
                    <div>
                      <p className="mb-1 text-xs font-medium text-muted">Sync Response Contract — POST /runtime/ask</p>
                      <p className="mb-2 text-[11px] text-muted">HTTP responses use the API envelope: <code>{'{ success, data }'}</code>.</p>
                      <JsonCodeBlock value={reference.sync_response_contract} maxHeight={520} actions={['copy', 'format']} />
                    </div>
                    <div>
                      <p className="mb-1 text-xs font-medium text-muted">Sync Response Example — {slotLabels[activeSlot]}</p>
                      <JsonCodeBlock value={reference.sync_response_example} maxHeight={520} actions={['copy', 'format']} />
                    </div>
                  </>
                )}

                {activeSection === 'stream' && (
                  <>
                    <div>
                      <p className="mb-1 text-xs font-medium text-muted">Streaming cURL — {slotLabels[activeSlot]}</p>
                      <ScrollArea orientation="horizontal" className="rounded-xl border border-border/80 bg-background/60">
                        <pre className="p-4 text-xs text-muted">{activeStreamCurl}</pre>
                      </ScrollArea>
                      <div className="mt-2"><CopyButton text={activeStreamCurl} /></div>
                    </div>
                    <div>
                      <p className="mb-1 text-xs font-medium text-muted">Streaming Response Contract — POST /runtime/ask/stream</p>
                      <p className="mb-2 text-[11px] text-muted">Streaming uses Server-Sent Events. The final <code>done</code> event carries the response object directly.</p>
                      <JsonCodeBlock value={reference.stream_events} maxHeight={620} actions={['copy', 'format']} />
                    </div>
                  </>
                )}

                {activeSection === 'structured' && (
                  <div>
                    <div className="mb-2 flex items-center gap-2">
                      <p className="text-xs font-medium text-muted">Structured Output — {slotLabels[activeSlot]}</p>
                      <Badge variant={reference.structured_output.enabled ? 'success' : 'secondary'} className="text-[10px]">
                        {reference.structured_output.enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </div>
                    <p className="mb-2 text-xs text-muted">Structured output is generated from the selected release snapshot, not from draft settings.</p>
                    <JsonCodeBlock value={reference.structured_output} maxHeight={620} actions={['copy', 'format']} />
                  </div>
                )}
              </div>
            </ScrollArea>
          </section>
        </div>
      </div>
    </div>
  )
}
