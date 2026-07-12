import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { CopyButton } from '@/components/common/CopyButton'
import { Badge } from '@/components/ui/Badge'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useReleases } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { API_BASE_URL } from '@/lib/api/client'
import { UI_LAYER_CLASS } from '@/lib/ui-layers'
import { ApiReferenceRuntimeKeySection } from './ApiReferenceRuntimeKeySection'
import {
  PUBLIC_RUNTIME_ENDPOINTS,
  buildApiReferenceForSlot,
  createJobCurl,
  getJobCurl,
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
  production: 'Production',
  staging: 'Staging',
}

type ApiSection = 'http' | 'stream' | 'jobs'

function CurlBlock({ value }: { value: string }) {
  return (
    <div>
      <ScrollArea orientation="horizontal" className="rounded-xl border border-border/80 bg-background/60">
        <pre className="p-4 text-xs text-muted">{value}</pre>
      </ScrollArea>
      <div className="mt-2"><CopyButton text={value} /></div>
    </div>
  )
}

function Endpoint({ method, path }: { method: string; path: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border/80 bg-background/45 p-2.5">
      <span className="text-[10px] font-semibold text-primary-light">{method}</span>
      <code className="min-w-0 flex-1 truncate text-[11px] text-white">{path}</code>
      <CopyButton text={`${method} ${path}`} />
    </div>
  )
}

export function ApiModal({ open, onClose, agent, orgProjectPathFn, projectId }: ApiModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const [activeSlot, setActiveSlot] = useState<RuntimeSlot>('production')
  const [activeSection, setActiveSection] = useState<ApiSection>('http')
  const [selectedKeyIds, setSelectedKeyIds] = useState<Record<RuntimeSlot, string | null>>({
    production: null,
    staging: null,
  })
  const { data: releases = [] } = useReleases(agent.id)

  useEffect(() => {
    if (!open) return
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
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

  useEffect(() => {
    if (!open) return
    setActiveSection('http')
    setActiveSlot(productionRelease ? 'production' : stagingRelease ? 'staging' : 'production')
  }, [open, productionRelease, stagingRelease])

  const activeRelease = activeSlot === 'production' ? productionRelease : stagingRelease
  const reference = useMemo(
    () => buildApiReferenceForSlot({ slot: activeSlot, release: activeRelease }),
    [activeSlot, activeRelease],
  )
  const syncCurl = useMemo(() => runtimeCurl(API_BASE_URL), [])
  const streamCurl = useMemo(() => runtimeCurl(API_BASE_URL, true), [])
  const jobCreateCurl = useMemo(() => createJobCurl(API_BASE_URL), [])
  const jobGetCurl = useMemo(() => getJobCurl(API_BASE_URL), [])

  const handleSelectedKeyId = useCallback((keyId: string | null) => {
    setSelectedKeyIds((current) => (
      current[activeSlot] === keyId ? current : { ...current, [activeSlot]: keyId }
    ))
  }, [activeSlot])

  if (!open) return null

  const sections: Array<{ id: ApiSection; label: string }> = [
    { id: 'http', label: 'HTTP' },
    { id: 'stream', label: 'Streaming' },
    { id: 'jobs', label: 'Jobs' },
  ]
  const manageKeysPath = orgProjectPathFn(projectId, 'api-keys')

  return createPortal(
    <div
      ref={overlayRef}
      className={`fixed inset-0 ${UI_LAYER_CLASS.modal} flex items-center justify-center bg-black/70 p-4 backdrop-blur-md`}
      onClick={(event) => { if (event.target === overlayRef.current) onClose() }}
    >
      <div className="flex h-[86vh] w-full max-w-[1180px] flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40">
        <div className="flex items-start justify-between gap-4 border-b border-border/90 bg-background/20 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-white">API Reference</h2>
            <p className="mt-0.5 text-[11px] text-muted">Integrate with the current immutable release through a Runtime Key.</p>
          </div>
          <button onClick={onClose} className="rounded-lg border border-transparent p-1 text-muted transition-colors hover:border-border/80 hover:bg-background/60 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-[320px_1fr]">
          <aside className="min-h-0 border-r border-border/90 bg-background/20 p-4">
            <ScrollArea className="h-full">
              <div className="space-y-4 pr-1">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Agent</p>
                  <div className="mt-2 rounded-xl border border-border/80 bg-background/45 p-3">
                    <p className="truncate text-sm font-medium text-white">{agent.name}</p>
                    <div className="mt-1 flex items-center gap-2">
                      <code className="min-w-0 flex-1 truncate text-[10px] text-muted">{agent.id}</code>
                      <CopyButton text={agent.id} />
                    </div>
                  </div>
                </div>

                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Environment</p>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    {(['production', 'staging'] as RuntimeSlot[]).map((slot) => {
                      const release = slot === 'production' ? productionRelease : stagingRelease
                      const active = activeSlot === slot
                      return (
                        <button
                          key={slot}
                          type="button"
                          onClick={() => setActiveSlot(slot)}
                          className={`rounded-xl border p-3 text-left transition-colors ${active ? 'border-primary/35 bg-primary/10' : 'border-border/80 bg-background/45 hover:border-primary/25'}`}
                        >
                          <p className="text-xs font-semibold text-white">{slotLabels[slot]}</p>
                          <p className="mt-1 text-[10px] text-muted">{release ? release.version : 'Not deployed'}</p>
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div className="rounded-xl border border-border/80 bg-background/45 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Active Release</p>
                      <p className="mt-1 text-sm font-medium text-white">{slotLabels[activeSlot]}</p>
                    </div>
                    <Badge variant={reference.available ? (activeSlot === 'production' ? 'success' : 'warning') : 'secondary'}>
                      {reference.release?.version ?? 'not deployed'}
                    </Badge>
                  </div>
                  {reference.release ? (
                    <>
                      <div className="mt-3 space-y-1 text-[11px] text-muted">
                        <p>Provider: <code className="text-white">{reference.release.provider}</code></p>
                        <p>Model: <code className="text-white">{reference.release.model}</code></p>
                        <p>Session: <code className="text-white">{reference.release.session_mode ?? 'default'}</code></p>
                      </div>
                      <p className="mt-3 text-[10px] leading-4 text-muted">This Runtime Key always uses the current {slotLabels[activeSlot]} release. Deploys and rollbacks do not require changing the key.</p>
                    </>
                  ) : (
                    <p className="mt-3 text-[11px] leading-4 text-yellow-300">Requests will return 409 until a {slotLabels[activeSlot]} release is deployed.</p>
                  )}
                </div>

                <ApiReferenceRuntimeKeySection
                  projectId={projectId}
                  agentId={agent.id}
                  agentName={agent.name}
                  environment={activeSlot}
                  manageKeysPath={manageKeysPath}
                  selectedKeyId={selectedKeyIds[activeSlot]}
                  onSelectedKeyId={handleSelectedKeyId}
                />
              </div>
            </ScrollArea>
          </aside>

          <section className="flex min-h-0 flex-col">
            <div className="flex gap-1 border-b border-border/90 bg-surface/70 p-1.5">
              {sections.map((section) => (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => setActiveSection(section.id)}
                  className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${activeSection === section.id ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/80 hover:bg-background/60 hover:text-white'}`}
                >
                  {section.label}
                </button>
              ))}
            </div>

            <ScrollArea className="min-h-0 flex-1">
              <div className="space-y-5 p-5">
                {activeSection === 'http' && (
                  <>
                    <div>
                      <p className="mb-2 text-xs font-medium text-muted">Endpoint</p>
                      <Endpoint method="POST" path={PUBLIC_RUNTIME_ENDPOINTS.http} />
                    </div>
                    <div className="grid gap-4 xl:grid-cols-2">
                      <div>
                        <p className="mb-2 text-xs font-medium text-muted">Minimal request</p>
                        <JsonCodeBlock value={reference.request} maxHeight={240} actions={['copy', 'format']} />
                      </div>
                      <div>
                        <p className="mb-2 text-xs font-medium text-muted">Continue a session</p>
                        <JsonCodeBlock value={reference.request_with_session} maxHeight={240} actions={['copy', 'format']} />
                      </div>
                    </div>
                    <div>
                      <p className="mb-2 text-xs font-medium text-muted">cURL</p>
                      <CurlBlock value={syncCurl} />
                    </div>
                    <div>
                      <p className="mb-2 text-xs font-medium text-muted">Response example</p>
                      <JsonCodeBlock value={reference.sync_response_example} maxHeight={520} actions={['copy', 'format']} />
                    </div>
                    {reference.structured_output.enabled && (
                      <div>
                        <div className="mb-2 flex items-center gap-2">
                          <p className="text-xs font-medium text-muted">Structured output from active release</p>
                          <Badge variant="success" className="text-[10px]">Enabled</Badge>
                        </div>
                        <JsonCodeBlock value={reference.structured_output} maxHeight={520} actions={['copy', 'format']} />
                      </div>
                    )}
                  </>
                )}

                {activeSection === 'stream' && (
                  <>
                    <div>
                      <p className="mb-2 text-xs font-medium text-muted">Endpoint</p>
                      <Endpoint method="POST" path={PUBLIC_RUNTIME_ENDPOINTS.stream} />
                    </div>
                    <div>
                      <p className="mb-2 text-xs font-medium text-muted">Streaming cURL</p>
                      <CurlBlock value={streamCurl} />
                    </div>
                    <div>
                      <p className="mb-2 text-xs font-medium text-muted">Server-Sent Events</p>
                      <JsonCodeBlock value={reference.stream_events} maxHeight={620} actions={['copy', 'format']} />
                    </div>
                  </>
                )}

                {activeSection === 'jobs' && (
                  <>
                    <div>
                      <p className="mb-2 text-xs font-medium text-muted">Create job</p>
                      <Endpoint method="POST" path={PUBLIC_RUNTIME_ENDPOINTS.jobs} />
                    </div>
                    <CurlBlock value={jobCreateCurl} />
                    <JsonCodeBlock value={reference.job_create_response} maxHeight={260} actions={['copy', 'format']} />
                    <div className="border-t border-border/80 pt-5">
                      <p className="mb-2 text-xs font-medium text-muted">Poll job</p>
                      <Endpoint method="GET" path={`${PUBLIC_RUNTIME_ENDPOINTS.jobs}/{job_id}`} />
                    </div>
                    <CurlBlock value={jobGetCurl} />
                    <JsonCodeBlock value={reference.job_status_response} maxHeight={520} actions={['copy', 'format']} />
                  </>
                )}
              </div>
            </ScrollArea>
          </section>
        </div>
      </div>
    </div>,
    document.body,
  )
}
