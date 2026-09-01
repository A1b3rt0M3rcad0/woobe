import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Bot, ChevronDown, KeyRound, Network, Plus, X } from 'lucide-react'
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

type RequestMode = 'minimal' | 'session'

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
      <div className="flex items-center justify-between border-b border-border/60 px-3 py-2">
        <span className="text-[10px] font-medium text-muted">Paste your Runtime Key and run</span>
        <CopyButton
          text={value}
          label="Copy code"
          copiedLabel="Copied"
          errorLabel="Unable to copy"
          className="px-2 py-1 text-[11px]"
        />
      </div>
      <ScrollArea orientation="horizontal">
        <pre className="min-w-max p-4 text-xs leading-5 text-slate-300">{value}</pre>
      </ScrollArea>
    </div>
  )
}

function Endpoint({ path }: { path: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border/75 bg-background/45 px-3 py-2.5">
      <span className="rounded-md border border-primary/25 bg-primary/10 px-2 py-1 text-[10px] font-semibold text-primary-light">POST</span>
      <code className="min-w-0 flex-1 truncate text-xs text-white">{path}</code>
      <CopyButton text={path} />
    </div>
  )
}

function DetailPanel({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <details className="group overflow-hidden rounded-xl border border-border/75 bg-background/35">
      <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3.5 text-left">
        <span className="min-w-0 flex-1">
          <span className="block text-xs font-semibold text-white">{title}</span>
          {description && <span className="mt-1 block text-[11px] leading-4 text-muted">{description}</span>}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-muted transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-border/65 p-4">{children}</div>
    </details>
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
  const [section, setSection] = useState<PublicRuntimeInterface>('http')
  const [requestMode, setRequestMode] = useState<RequestMode>('minimal')
  const [language, setLanguage] = useState<RuntimeCodeLanguage>('python')
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null)
  const [showCreateKey, setShowCreateKey] = useState(false)

  useEffect(() => {
    if (!open) return
    setEnvironment(environments.production.available ? 'production' : environments.staging.available ? 'staging' : 'production')
    setSection('http')
    setRequestMode('minimal')
    setLanguage('python')
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
  const sessionRequestAvailable = Boolean(reference.requestWithSession)
  const requestPayload = requestMode === 'session' && reference.requestWithSession
    ? reference.requestWithSession
    : reference.request
  const snippet = buildRuntimeSnippet({
    language,
    runtimeInterface: section,
    baseUrl: API_BASE_URL,
    body: requestPayload,
    includeIdempotencyKey: targetType === 'network',
  })
  const endpointPath = section === 'stream' ? '/v1/run/stream' : '/v1/run'
  const targetLabel = targetType === 'network' ? 'Network' : 'Agent'
  const TargetIcon = targetType === 'network' ? Network : Bot
  const managePath = `${manageKeysPath}?type=runtime&targetType=${targetType}&target=${encodeURIComponent(targetId)}&environment=${environment}${selectedKey ? `&credential=${encodeURIComponent(selectedKey.credential_id)}` : ''}`

  return createPortal(
    <div
      ref={overlayRef}
      className={`fixed inset-0 ${UI_LAYER_CLASS.modal} flex items-center justify-center bg-black/75 p-4 backdrop-blur-md`}
      onClick={(event) => { if (event.target === overlayRef.current) onClose() }}
    >
      <div className="flex h-[88vh] w-full max-w-[1180px] flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40">
        <header className="flex shrink-0 items-start gap-4 border-b border-border/90 bg-background/20 px-5 py-4">
          <div className="min-w-0">
            <p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-primary-light">{targetLabel} runtime</p>
            <h2 className="mt-1 truncate text-base font-semibold text-white">{targetName} · API Reference</h2>
            <p className="mt-1 text-[11px] text-muted">Copy a short request and use the documented response format to process the result.</p>
          </div>
          <button type="button" onClick={onClose} className="ml-auto rounded-lg p-1.5 text-muted hover:bg-background/70 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="grid min-h-0 flex-1 grid-cols-[290px_minmax(0,1fr)]">
          <aside className="min-h-0 border-r border-border/90 bg-background/20">
            <ScrollArea className="h-full">
              <div className="space-y-5 p-4">
                {sidebarHeader}

                <section className="rounded-xl border border-border/75 bg-background/35 p-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light">
                      <TargetIcon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-white">{targetName}</p>
                      <p className="mt-1 text-[10px] text-muted">{targetLabel} Runtime</p>
                    </div>
                  </div>
                </section>

                <section>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Environment</p>
                  <div className="mt-2 grid grid-cols-2 rounded-xl border border-border/75 bg-background/35 p-1">
                    {(['production', 'staging'] as RuntimeEnvironment[]).map((item) => (
                      <button
                        key={item}
                        type="button"
                        onClick={() => {
                          setEnvironment(item)
                          setSelectedKeyId(null)
                          setRequestMode('minimal')
                        }}
                        className={cn(
                          'rounded-lg px-3 py-2 text-xs font-medium transition-colors',
                          item === environment
                            ? 'bg-primary/12 text-primary-light shadow-sm'
                            : 'text-muted hover:bg-background/60 hover:text-white',
                        )}
                      >
                        {environmentLabels[item]}
                      </button>
                    ))}
                  </div>
                  <div className="mt-2 flex items-center gap-2 rounded-lg border border-border/60 bg-background/25 px-3 py-2 text-[11px] text-muted">
                    <span className={cn('h-1.5 w-1.5 rounded-full', reference.available ? 'bg-emerald-400' : 'bg-amber-400')} />
                    <span className="min-w-0 flex-1 truncate">
                      {reference.available ? reference.version ?? 'Deployment active' : 'Not deployed'}
                    </span>
                  </div>
                  {reference.warning && (
                    <div className="mt-2 rounded-lg border border-amber-400/15 bg-amber-400/5 px-3 py-2.5 text-[10px] leading-4 text-amber-200">
                      {reference.warning}
                    </div>
                  )}
                </section>

                <section>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">{targetLabel} Runtime Key</p>
                  {compatibleKeys.length > 0 ? (
                    <div className="mt-2 space-y-2">
                      <select
                        value={selectedKeyId ?? ''}
                        onChange={(event) => setSelectedKeyId(event.target.value || null)}
                        className="h-10 w-full rounded-lg border border-border/75 bg-background/55 px-3 text-xs text-white outline-none focus:border-primary/40"
                      >
                        {compatibleKeys.map((key) => <option key={key.id} value={key.id}>{key.name}</option>)}
                      </select>
                      {selectedKey && (
                        <div className="rounded-lg border border-border/70 bg-background/30 px-3 py-2.5">
                          <div className="flex items-center gap-2">
                            <KeyRound className="h-3.5 w-3.5 text-primary-light" />
                            <code className="min-w-0 flex-1 truncate text-[11px] text-white">{selectedKey.key_prefix}...</code>
                          </div>
                          <p className="mt-1 text-[10px] text-muted">{selectedKey.interfaces.join(' · ')}</p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="mt-2 rounded-xl border border-dashed border-border/75 bg-background/25 p-3">
                      <p className="text-xs font-medium text-white">No compatible Runtime Key</p>
                      <p className="mt-1 text-[11px] leading-4 text-muted">Create a key for this {targetLabel.toLowerCase()} and {environmentLabels[environment]}.</p>
                      <Button className="mt-3 w-full" size="sm" onClick={() => setShowCreateKey(true)}>
                        <Plus className="mr-2 h-3.5 w-3.5" /> Create Runtime Key
                      </Button>
                    </div>
                  )}
                  <Link to={managePath} className="mt-2 inline-flex text-[11px] text-muted hover:text-white">Manage keys</Link>
                </section>
              </div>
            </ScrollArea>
          </aside>

          <section className="flex min-h-0 flex-col">
            <div className="flex shrink-0 items-center border-b border-border/90 bg-surface/55 px-4 py-2.5">
              <div className="inline-flex rounded-lg border border-border/70 bg-background/35 p-0.5">
                {([['http', 'HTTP'], ['stream', 'Streaming']] as Array<[PublicRuntimeInterface, string]>).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setSection(id)}
                    className={cn(
                      'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                      section === id ? 'bg-primary/12 text-primary-light' : 'text-muted hover:text-white',
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="ml-auto flex items-center gap-2 text-[10px] text-muted/70">
                <span>Jobs</span>
                <span className="rounded-full border border-border/70 bg-background/45 px-2 py-0.5 uppercase tracking-wide">Coming soon</span>
              </div>
            </div>

            <ScrollArea className="min-h-0 flex-1">
              <div className="space-y-6 p-5">
                <section>
                  <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Endpoint</p>
                  <Endpoint path={endpointPath} />
                </section>

                <section>
                  <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Request</p>
                      <p className="mt-1 text-[11px] text-muted">This JSON body is already included in the code example.</p>
                    </div>
                    <div className="inline-flex rounded-lg border border-border/70 bg-background/35 p-0.5">
                      <button
                        type="button"
                        onClick={() => setRequestMode('minimal')}
                        className={cn(
                          'rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors',
                          requestMode === 'minimal' ? 'bg-primary/12 text-primary-light' : 'text-muted hover:text-white',
                        )}
                      >
                        First Run
                      </button>
                      {sessionRequestAvailable ? (
                        <button
                          type="button"
                          onClick={() => setRequestMode('session')}
                          className={cn(
                            'rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors',
                            requestMode === 'session' ? 'bg-primary/12 text-primary-light' : 'text-muted hover:text-white',
                          )}
                        >
                          Continue session
                        </button>
                      ) : (
                        <span className="px-2.5 py-1.5 text-[10px] text-muted/60">Stateless</span>
                      )}
                    </div>
                  </div>
                  <JsonCodeBlock value={requestPayload} maxHeight={220} actions={['copy', 'format']} />
                </section>

                <section>
                  <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Code example</p>
                      <p className="mt-1 text-[11px] text-muted">
                        {section === 'stream'
                          ? 'Reads and prints each SSE event exactly as the Runtime emits it.'
                          : 'Sends one request and prints the complete HTTP response.'}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-1">
                      {RUNTIME_CODE_LANGUAGES.map((item) => (
                        <button
                          key={item.value}
                          type="button"
                          onClick={() => setLanguage(item.value)}
                          className={cn(
                            'rounded-lg border px-2.5 py-1.5 text-[11px] font-medium transition-colors',
                            language === item.value
                              ? 'border-primary/30 bg-primary/10 text-primary-light'
                              : 'border-border/65 bg-background/30 text-muted hover:text-white',
                          )}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <CodeBlock value={snippet} />
                  <p className="mt-2 text-[10px] leading-4 text-muted">Do not commit Runtime Keys to source control.</p>
                </section>

                <section>
                  <div className="mb-2">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
                      {section === 'stream' ? 'Event format' : 'Response format'}
                    </p>
                    <p className="mt-1 text-[11px] leading-4 text-muted">
                      {section === 'stream'
                        ? 'Each SSE frame has an event name and a JSON data payload. Route behavior by event and parse data as JSON.'
                        : 'The HTTP endpoint returns one JSON envelope. The public answer and structured output are inside data.'}
                    </p>
                  </div>
                  <JsonCodeBlock
                    value={section === 'stream' ? reference.streamEvents : reference.response}
                    maxHeight={520}
                    actions={['copy', 'format']}
                  />
                </section>

                {(reference.outputContract != null || reference.manifest?.length || reference.note || targetType === 'network') && (
                  <section className="space-y-2">
                    <div className="pb-1">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Advanced</p>
                      <p className="mt-1 text-[11px] text-muted">Deployment contracts and operational semantics.</p>
                    </div>

                    {reference.outputContract != null && (
                      <DetailPanel title="Public output contract" description="Schema enforced when structured output is enabled.">
                        <JsonCodeBlock value={reference.outputContract} maxHeight={360} actions={['copy', 'format']} />
                      </DetailPanel>
                    )}

                    {reference.manifest && reference.manifest.length > 0 && (
                      <DetailPanel title="Agent Release manifest" description="Immutable Agent Releases included in this Network deployment.">
                        <div className="grid gap-2 sm:grid-cols-2">
                          {reference.manifest.map((item) => (
                            <div key={item.id} className="rounded-xl border border-border/70 bg-background/35 p-3">
                              <div className="flex items-center justify-between gap-2">
                                <p className="truncate text-[11px] font-medium text-white">{item.name}</p>
                                <code className="shrink-0 text-[9px] text-primary-light">{item.version}</code>
                              </div>
                              {item.role && <p className="mt-1 text-[9px] uppercase tracking-[0.12em] text-muted">{item.role}</p>}
                            </div>
                          ))}
                        </div>
                      </DetailPanel>
                    )}

                    {reference.note && (
                      <DetailPanel title="Runtime behavior" description="How the Runtime Key resolves releases and deployment changes.">
                        <p className="text-[11px] leading-5 text-muted">{reference.note}</p>
                      </DetailPanel>
                    )}

                    {targetType === 'network' && (
                      <DetailPanel title="Network Run semantics" description="Relationship between the Network Run and delegated Agent Runs.">
                        <p className="text-[11px] leading-5 text-muted">
                          Every request creates one Network Run. The public result belongs to the Network, while delegated Agent Runs remain attributable inside its Trace.
                        </p>
                      </DetailPanel>
                    )}
                  </section>
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
