import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Bot, Copy, KeyRound, Network, Plus, X } from 'lucide-react'
import { Link } from 'react-router-dom'

import { CopyButton } from '@/components/common/CopyButton'
import { Button } from '@/components/ui/Button'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { CreateApiKeyDialog } from '@/features/api-keys/components/CreateApiKeyDialog'
import { useApiKeys } from '@/features/api-keys/hooks'
import type { ApiKey, RuntimeEnvironment, RuntimeTargetType } from '@/features/api-keys/types'
import { API_BASE_URL } from '@/lib/api/client'
import { UI_LAYER_CLASS } from '@/lib/ui-layers'
import { cn } from '@/lib/utils'
import {
  buildRuntimeSnippet,
  RUNTIME_CODE_LANGUAGES,
  type PublicRuntimeInterface,
  type RuntimeCodeLanguage,
} from './runtime-snippets'

export interface RuntimeReferenceManifestItem {
  id: string
  name: string
  version: string
  role?: string | null
}

export interface RuntimeEnvironmentReference {
  available: boolean
  version: string | null
  summary: Array<{ label: string; value: string }>
  request: Record<string, unknown>
  requestWithSession?: Record<string, unknown> | null
  response: unknown
  streamEvents: unknown
  outputContract?: unknown
  manifest?: RuntimeReferenceManifestItem[]
  warning?: string | null
  note?: string | null
}

interface RuntimeApiReferenceModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  targetType: RuntimeTargetType
  targetId: string
  targetName: string
  manageKeysPath: string
  environments: Record<RuntimeEnvironment, RuntimeEnvironmentReference>
  sidebarHeader?: ReactNode
}

type ApiSection = PublicRuntimeInterface | 'jobs'

const environmentLabels: Record<RuntimeEnvironment, string> = {
  production: 'Production',
  staging: 'Staging',
}

function runtimeKeyTargetType(key: ApiKey): RuntimeTargetType | null {
  if (key.target_type === 'agent' || key.target_type === 'network') return key.target_type
  return key.agent_id ? 'agent' : null
}

function runtimeKeyTargetId(key: ApiKey): string | null {
  return key.target_id ?? key.agent_id ?? null
}

function CodeBlock({ value }: { value: string }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border/80 bg-background/60">
      <div className="flex items-center justify-end border-b border-border/70 px-3 py-2">
        <button
          type="button"
          onClick={() => void navigator.clipboard?.writeText(value)}
          className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted hover:text-white"
        >
          <Copy className="h-3.5 w-3.5" /> Copy
        </button>
      </div>
      <ScrollArea orientation="horizontal">
        <pre className="min-w-max p-4 text-xs leading-5 text-slate-300">{value}</pre>
      </ScrollArea>
    </div>
  )
}

function Endpoint({ path }: { path: string }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-border/80 bg-background/55 p-3">
      <span className="rounded-md border border-primary/25 bg-primary/10 px-2 py-1 text-[10px] font-semibold text-primary-light">POST</span>
      <code className="min-w-0 flex-1 truncate text-xs text-white">{path}</code>
      <CopyButton text={path} />
    </div>
  )
}

export function RuntimeApiReferenceModal({
  open,
  onClose,
  projectId,
  targetType,
  targetId,
  targetName,
  manageKeysPath,
  environments,
  sidebarHeader,
}: RuntimeApiReferenceModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const { data: apiKeys = [] } = useApiKeys(projectId)
  const [environment, setEnvironment] = useState<RuntimeEnvironment>('production')
  const [section, setSection] = useState<ApiSection>('http')
  const [language, setLanguage] = useState<RuntimeCodeLanguage>('curl')
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null)
  const [showCreateKey, setShowCreateKey] = useState(false)

  useEffect(() => {
    if (!open) return
    const nextEnvironment = environments.production.available
      ? 'production'
      : environments.staging.available
        ? 'staging'
        : 'production'
    setEnvironment(nextEnvironment)
    setSection('http')
    setLanguage('curl')
  }, [environments.production.available, environments.staging.available, open])

  useEffect(() => {
    if (!open) return
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose, open])

  const compatibleKeys = useMemo(() => apiKeys.filter((key) => (
    key.kind === 'runtime'
    && key.status === 'active'
    && runtimeKeyTargetType(key) === targetType
    && runtimeKeyTargetId(key) === targetId
    && key.environment === environment
  )), [apiKeys, environment, targetId, targetType])

  useEffect(() => {
    if (selectedKeyId && compatibleKeys.some((key) => key.id === selectedKeyId)) return
    setSelectedKeyId(compatibleKeys[0]?.id ?? null)
  }, [compatibleKeys, selectedKeyId])

  if (!open) return null

  const reference = environments[environment]
  const selectedKey = compatibleKeys.find((key) => key.id === selectedKeyId) ?? null
  const activeRuntimeInterface: PublicRuntimeInterface = section === 'stream' ? 'stream' : 'http'
  const requestBody = reference.requestWithSession ?? reference.request
  const snippet = buildRuntimeSnippet({
    language,
    runtimeInterface: activeRuntimeInterface,
    baseUrl: API_BASE_URL,
    body: requestBody,
    includeIdempotencyKey: targetType === 'network',
  })
  const endpointPath = activeRuntimeInterface === 'stream' ? '/v1/run/stream' : '/v1/run'
  const targetLabel = targetType === 'network' ? 'Network' : 'Agent'
  const TargetIcon = targetType === 'network' ? Network : Bot
  const managePath = `${manageKeysPath}?type=runtime&targetType=${targetType}&target=${encodeURIComponent(targetId)}&environment=${environment}${selectedKey ? `&credential=${encodeURIComponent(selectedKey.credential_id)}` : ''}`

  return createPortal(
    <div
      ref={overlayRef}
      className={`fixed inset-0 ${UI_LAYER_CLASS.modal} flex items-center justify-center bg-black/75 p-4 backdrop-blur-md`}
      onClick={(event) => { if (event.target === overlayRef.current) onClose() }}
    >
      <div className="flex h-[88vh] w-full max-w-[1240px] flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40">
        <header className="flex shrink-0 items-start gap-4 border-b border-border/90 bg-background/20 px-5 py-4">
          <div className="min-w-0">
            <p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-primary-light">{targetLabel} runtime</p>
            <h2 className="mt-1 truncate text-base font-semibold text-white">{targetName} · API Reference</h2>
            <p className="mt-1 text-[11px] text-muted">The Runtime Key resolves the target, environment and current immutable deployment.</p>
          </div>
          <button type="button" onClick={onClose} className="ml-auto rounded-lg p-1.5 text-muted hover:bg-background/70 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="grid min-h-0 flex-1 grid-cols-[340px_minmax(0,1fr)]">
          <aside className="min-h-0 border-r border-border/90 bg-background/20">
            <ScrollArea className="h-full">
              <div className="space-y-4 p-4">
                {sidebarHeader}

                <section>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">{targetLabel}</p>
                  <div className="mt-2 rounded-xl border border-border/80 bg-background/45 p-3">
                    <div className="flex items-center gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light">
                        <TargetIcon className="h-4 w-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-white">{targetName}</p>
                        <code className="mt-1 block truncate text-[10px] text-muted">{targetId}</code>
                      </div>
                      <CopyButton text={targetId} />
                    </div>
                  </div>
                </section>

                <section>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Environment</p>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    {(['production', 'staging'] as RuntimeEnvironment[]).map((item) => {
                      const itemReference = environments[item]
                      return (
                        <button
                          key={item}
                          type="button"
                          onClick={() => { setEnvironment(item); setSelectedKeyId(null) }}
                          className={cn(
                            'rounded-xl border p-3 text-left transition-colors',
                            item === environment
                              ? 'border-primary/40 bg-primary/10'
                              : 'border-border/80 bg-background/45 hover:border-primary/25',
                          )}
                        >
                          <p className="text-xs font-semibold text-white">{environmentLabels[item]}</p>
                          <p className="mt-1 truncate font-mono text-[10px] text-muted">{itemReference.version ?? 'Not deployed'}</p>
                        </button>
                      )
                    })}
                  </div>
                </section>

                <section className="rounded-xl border border-border/80 bg-background/45 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Active deployment</p>
                      <p className="mt-1 text-sm font-medium text-white">{environmentLabels[environment]}</p>
                    </div>
                    <span className={cn(
                      'rounded-full border px-2 py-1 text-[10px] font-medium',
                      reference.available
                        ? 'border-primary/25 bg-primary/10 text-primary-light'
                        : 'border-border bg-background text-muted',
                    )}>
                      {reference.version ?? 'not deployed'}
                    </span>
                  </div>
                  <div className="mt-3 space-y-1.5">
                    {reference.summary.map((item) => (
                      <p key={item.label} className="flex items-start justify-between gap-3 text-[11px] text-muted">
                        <span>{item.label}</span>
                        <code className="max-w-[190px] truncate text-right text-white">{item.value}</code>
                      </p>
                    ))}
                  </div>
                  {reference.warning && <p className="mt-3 text-[11px] leading-4 text-amber-200">{reference.warning}</p>}
                  {reference.note && <p className="mt-3 text-[10px] leading-4 text-muted">{reference.note}</p>}
                </section>

                {reference.outputContract != null && (
                  <section className="rounded-xl border border-border/80 bg-background/45 p-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Public output contract</p>
                    <div className="mt-2">
                      <JsonCodeBlock value={reference.outputContract} maxHeight={220} actions={['copy', 'format']} />
                    </div>
                  </section>
                )}

                {reference.manifest && reference.manifest.length > 0 && (
                  <section>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Agent Release manifest</p>
                    <div className="mt-2 space-y-2">
                      {reference.manifest.map((item) => (
                        <div key={item.id} className="rounded-xl border border-border/80 bg-background/45 p-2.5">
                          <div className="flex items-center justify-between gap-2">
                            <p className="truncate text-[11px] font-medium text-white">{item.name}</p>
                            <code className="shrink-0 text-[9px] text-primary-light">{item.version}</code>
                          </div>
                          {item.role && <p className="mt-1 text-[9px] uppercase tracking-[0.12em] text-muted">{item.role}</p>}
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                <section>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">{targetLabel} Runtime Key</p>
                    <button type="button" onClick={() => setShowCreateKey(true)} className="inline-flex items-center gap-1 text-[11px] font-medium text-primary-light hover:text-white">
                      <Plus className="h-3.5 w-3.5" /> Create
                    </button>
                  </div>
                  {compatibleKeys.length > 0 ? (
                    <div className="mt-2 space-y-2">
                      <select
                        value={selectedKeyId ?? ''}
                        onChange={(event) => setSelectedKeyId(event.target.value || null)}
                        className="h-10 w-full rounded-lg border border-border/80 bg-background/70 px-3 text-xs text-white outline-none focus:border-primary/40"
                      >
                        {compatibleKeys.map((key) => <option key={key.id} value={key.id}>{key.name}</option>)}
                      </select>
                      {selectedKey && (
                        <div className="rounded-lg border border-border/80 bg-background/45 p-2.5">
                          <div className="flex items-center gap-2">
                            <KeyRound className="h-3.5 w-3.5 text-primary-light" />
                            <code className="min-w-0 flex-1 truncate text-[11px] text-white">{selectedKey.key_prefix}...</code>
                          </div>
                          <p className="mt-1 text-[10px] text-muted">{selectedKey.interfaces.join(' · ')}</p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="mt-2 rounded-xl border border-dashed border-border/80 bg-background/35 p-3">
                      <p className="text-xs font-medium text-white">No compatible Runtime Key</p>
                      <p className="mt-1 text-[11px] leading-4 text-muted">Create a key bound to this {targetLabel.toLowerCase()} and {environmentLabels[environment]}.</p>
                      <Button className="mt-3 w-full" size="sm" onClick={() => setShowCreateKey(true)}>
                        <Plus className="mr-2 h-3.5 w-3.5" /> Create {targetLabel} Key
                      </Button>
                    </div>
                  )}
                  <Link to={managePath} className="mt-2 inline-flex text-[11px] text-muted hover:text-white">Manage this {targetLabel}&apos;s keys</Link>
                </section>
              </div>
            </ScrollArea>
          </aside>

          <section className="flex min-h-0 flex-col">
            <div className="flex shrink-0 items-center gap-1 border-b border-border/90 bg-surface/70 p-1.5">
              {([
                ['http', 'HTTP'],
                ['stream', 'Streaming'],
              ] as Array<[ApiSection, string]>).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setSection(id)}
                  className={cn(
                    'rounded-lg border px-3 py-2 text-xs font-medium transition-colors',
                    section === id
                      ? 'border-primary/35 bg-primary/10 text-primary-light'
                      : 'border-transparent text-muted hover:border-border/80 hover:bg-background/60 hover:text-white',
                  )}
                >
                  {label}
                </button>
              ))}
              <button type="button" disabled className="ml-1 inline-flex cursor-not-allowed items-center gap-2 rounded-lg border border-border/60 px-3 py-2 text-xs font-medium text-muted/65">
                Jobs <span className="rounded-full border border-border/70 bg-background/60 px-1.5 py-0.5 text-[9px] uppercase tracking-wide">Coming soon</span>
              </button>
            </div>

            <ScrollArea className="min-h-0 flex-1">
              <div className="space-y-5 p-5">
                <div>
                  <p className="mb-2 text-xs font-medium text-muted">Endpoint</p>
                  <Endpoint path={endpointPath} />
                </div>

                <div className="grid gap-4 xl:grid-cols-2">
                  <div>
                    <p className="mb-2 text-xs font-medium text-muted">Minimal request</p>
                    <JsonCodeBlock value={reference.request} maxHeight={260} actions={['copy', 'format']} />
                  </div>
                  <div>
                    <p className="mb-2 text-xs font-medium text-muted">Continue a session</p>
                    {reference.requestWithSession ? (
                      <JsonCodeBlock value={reference.requestWithSession} maxHeight={260} actions={['copy', 'format']} />
                    ) : (
                      <div className="flex min-h-[150px] items-center rounded-xl border border-border/80 bg-background/45 p-4 text-xs leading-5 text-muted">This deployment is stateless. Every request is independent and does not persist a Session.</div>
                    )}
                  </div>
                </div>

                <div>
                  <div className="mb-2 flex flex-wrap items-center gap-1">
                    {RUNTIME_CODE_LANGUAGES.map((item) => (
                      <button
                        key={item.value}
                        type="button"
                        onClick={() => setLanguage(item.value)}
                        className={cn(
                          'rounded-lg border px-2.5 py-1.5 text-[11px] font-medium transition-colors',
                          language === item.value
                            ? 'border-primary/35 bg-primary/10 text-primary-light'
                            : 'border-border/70 bg-background/45 text-muted hover:text-white',
                        )}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                  <CodeBlock value={snippet} />
                </div>

                <div>
                  <p className="mb-2 text-xs font-medium text-muted">{section === 'stream' ? 'Server-Sent Events' : 'Response example'}</p>
                  <JsonCodeBlock value={section === 'stream' ? reference.streamEvents : reference.response} maxHeight={620} actions={['copy', 'format']} />
                </div>

                {targetType === 'network' && (
                  <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-[11px] leading-5 text-muted">
                    Every request creates one Network Run. The response exposes the Network execution identity, while delegated Agent Runs remain attributable inside the Network Run and its Trace.
                  </div>
                )}
              </div>
            </ScrollArea>
          </section>
        </div>
      </div>

      <CreateApiKeyDialog
        open={showCreateKey}
        onClose={() => setShowCreateKey(false)}
        projectId={projectId}
        initialKind="runtime"
        lockedTargetType={targetType}
        lockedTargetId={targetId}
        initialEnvironment={environment}
        layer="nestedModal"
        onCreated={(key) => setSelectedKeyId(key.id)}
      />
    </div>,
    document.body,
  )
}
