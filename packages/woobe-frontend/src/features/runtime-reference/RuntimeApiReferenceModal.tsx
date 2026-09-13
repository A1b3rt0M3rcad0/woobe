import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Bot, ChevronDown, KeyRound, Network, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  CodePanel,
  EmptyStatePanel,
  Field,
  FieldDescription,
  FieldLabel,
  SectionBlock,
  SegmentedControl,
  TechnicalListItem,
  woobeLayout,
} from '@woobe/ui'

import { CopyButton } from '@/components/common/CopyButton'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { Select } from '@/components/ui/Select'
import { CreateApiKeyDialog } from '@/features/api-keys/components/CreateApiKeyDialog'
import { useApiKeys } from '@/features/api-keys/hooks'
import type { ApiKey, RuntimeEnvironment, RuntimeTargetType } from '@/features/api-keys/types'
import { API_BASE_URL } from '@/lib/api/client'
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

function CodeExample({ value, language }: { value: string; language: string }) {
  return (
    <CodePanel
      title="Code example"
      badge={language}
      density="compact"
      actions={(
        <CopyButton
          text={value}
          label="Copy code"
          copiedLabel="Copied"
          errorLabel="Unable to copy"
        />
      )}
    >
      <ScrollArea orientation="horizontal">
        <pre className="min-w-max bg-background/20 p-ui-lg font-mono text-system-control leading-5 text-slate-300">{value}</pre>
      </ScrollArea>
    </CodePanel>
  )
}

function Endpoint({ path }: { path: string }) {
  return (
    <CodePanel
      title="Endpoint"
      badge="POST"
      density="compact"
      actions={<CopyButton text={path} />}
    >
      <div className="px-ui-lg py-ui-md">
        <code className="break-all font-mono text-system-control text-accent-foreground">{path}</code>
      </div>
    </CodePanel>
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
    <details className="group overflow-hidden rounded-container border border-border bg-background/25">
      <summary className="flex cursor-pointer list-none items-center gap-ui-md px-ui-md py-ui-sm text-left focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40">
        <span className="min-w-0 flex-1">
          <span className="block font-mono text-system-control font-semibold text-accent-foreground">{title}</span>
          {description ? <span className="mt-ui-xs block font-sans text-product-caption text-muted-foreground">{description}</span> : null}
        </span>
        <ChevronDown className="h-icon w-icon shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-border p-ui-md">{children}</div>
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

  const environmentItems = (['production', 'staging'] as RuntimeEnvironment[]).map((item) => ({
    value: item,
    label: environmentLabels[item],
  }))

  const interfaceItems = [
    { value: 'http', label: 'HTTP' },
    { value: 'stream', label: 'Streaming' },
  ]

  const requestModeItems = [
    { value: 'minimal', label: 'First Run' },
    ...(sessionRequestAvailable ? [{ value: 'session', label: 'Continue session' }] : []),
  ]

  const languageItems = RUNTIME_CODE_LANGUAGES.map((item) => ({ value: item.value, label: item.label }))

  return (
    <>
      <Dialog
        open={open}
        onClose={showCreateKey ? () => undefined : onClose}
        title={`${targetName} · API Reference`}
        className="flex max-h-dialog max-w-dialog-wide flex-col overflow-hidden"
        contentClassName="min-h-0 flex-1 p-0"
      >
        <div className="flex h-full min-h-0 flex-col lg:flex-row">
          <aside className="shrink-0 border-b border-border bg-background/20 lg:w-dialog-sidebar lg:border-b-0 lg:border-r">
            <ScrollArea className="max-h-72 lg:h-full lg:max-h-none">
              <div className="grid gap-ui-lg p-ui-md">
                {sidebarHeader}

                <TechnicalListItem
                  label={targetName}
                  description={`${targetLabel} Runtime`}
                  meta={targetId}
                  leading={(
                    <span className="flex h-control-navigation w-control-navigation items-center justify-center rounded-control border border-primary/25 bg-primary/[0.08] text-primary-light">
                      <TargetIcon className="h-icon w-icon" />
                    </span>
                  )}
                />

                <Field>
                  <FieldLabel>Environment</FieldLabel>
                  <SegmentedControl
                    items={environmentItems}
                    value={environment}
                    onValueChange={(value) => {
                      setEnvironment(value as RuntimeEnvironment)
                      setSelectedKeyId(null)
                      setRequestMode('minimal')
                    }}
                    ariaLabel="Runtime environment"
                    stretch
                    size="compact"
                  />
                  <div className="flex items-center justify-between gap-ui-sm">
                    <FieldDescription>{reference.version ?? (reference.available ? 'Deployment active' : 'Not deployed')}</FieldDescription>
                    <Badge variant={reference.available ? 'success' : 'warning'} size="compact">
                      {reference.available ? 'Available' : 'Unavailable'}
                    </Badge>
                  </div>
                </Field>

                {reference.warning ? (
                  <Alert variant="warning">
                    <AlertTitle>Environment warning</AlertTitle>
                    <AlertDescription>{reference.warning}</AlertDescription>
                  </Alert>
                ) : null}

                <Field>
                  <FieldLabel>{targetLabel} Runtime Key</FieldLabel>
                  {compatibleKeys.length > 0 ? (
                    <div className="grid gap-ui-sm">
                      <Select
                        value={selectedKeyId ?? ''}
                        onChange={(event) => setSelectedKeyId(event.target.value || null)}
                        options={compatibleKeys.map((key) => ({ value: key.id, label: key.name }))}
                      />
                      {selectedKey ? (
                        <TechnicalListItem
                          label={`${selectedKey.key_prefix}...`}
                          description={selectedKey.name}
                          meta={selectedKey.interfaces.join(' · ')}
                          leading={<KeyRound className="h-icon w-icon text-primary-light" />}
                        />
                      ) : null}
                    </div>
                  ) : (
                    <EmptyStatePanel
                      compact
                      icon={<KeyRound className="h-icon-lg w-icon-lg" />}
                      title="No compatible Runtime Key"
                      description={`Create a key for this ${targetLabel.toLowerCase()} and ${environmentLabels[environment]}.`}
                      action={(
                        <Button size="sm" onClick={() => setShowCreateKey(true)}>
                          <Plus className="mr-2 h-icon w-icon" />Create Runtime Key
                        </Button>
                      )}
                    />
                  )}
                  <Link to={managePath} className="inline-flex font-mono text-system-label text-muted-foreground transition-colors hover:text-accent-foreground">
                    Manage keys
                  </Link>
                </Field>
              </div>
            </ScrollArea>
          </aside>

          <section className="flex min-h-0 min-w-0 flex-1 flex-col">
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-ui-sm border-b border-border bg-surface/55 px-ui-md py-ui-sm">
              <SegmentedControl
                items={interfaceItems}
                value={section}
                onValueChange={(value) => setSection(value as PublicRuntimeInterface)}
                ariaLabel="Runtime interface"
                size="compact"
              />
              <div className="flex items-center gap-ui-sm">
                <span className="font-mono text-system-meta text-muted-foreground">Jobs</span>
                <Badge variant="outline" size="compact">Coming soon</Badge>
              </div>
            </div>

            <ScrollArea className="min-h-0 flex-1">
              <div className="grid gap-ui-lg p-ui-lg">
                <Endpoint path={endpointPath} />

                <SectionBlock
                  title="Request"
                  description="This JSON body is already included in the code example."
                  density="compact"
                  actions={(
                    <div className="flex items-center gap-ui-sm">
                      <SegmentedControl
                        items={requestModeItems}
                        value={requestMode}
                        onValueChange={(value) => setRequestMode(value as RequestMode)}
                        ariaLabel="Request example mode"
                        size="compact"
                      />
                      {!sessionRequestAvailable ? <Badge variant="outline" size="compact">Stateless</Badge> : null}
                    </div>
                  )}
                >
                  <JsonCodeBlock value={requestPayload} maxHeight={woobeLayout.codeStructuredDefault} actions={['copy', 'format']} />
                </SectionBlock>

                <SectionBlock
                  title="Code example"
                  description={section === 'stream'
                    ? 'Reads and prints each SSE event exactly as the Runtime emits it.'
                    : 'Sends one request and prints the complete HTTP response.'}
                  density="compact"
                  actions={(
                    <div className="max-w-full overflow-x-auto">
                      <SegmentedControl
                        items={languageItems}
                        value={language}
                        onValueChange={(value) => setLanguage(value as RuntimeCodeLanguage)}
                        ariaLabel="Code language"
                        size="compact"
                      />
                    </div>
                  )}
                >
                  <div className="grid gap-ui-sm">
                    <CodeExample value={snippet} language={RUNTIME_CODE_LANGUAGES.find((item) => item.value === language)?.label ?? language} />
                    <Alert variant="info">
                      <AlertDescription>Do not commit Runtime Keys to source control.</AlertDescription>
                    </Alert>
                  </div>
                </SectionBlock>

                <SectionBlock
                  title={section === 'stream' ? 'Event format' : 'Response format'}
                  description={section === 'stream'
                    ? 'Each SSE frame has an event name and a JSON data payload. Route behavior by event and parse data as JSON.'
                    : 'The HTTP endpoint returns one JSON envelope. The public answer and structured output are inside data.'}
                  density="compact"
                >
                  <JsonCodeBlock
                    value={section === 'stream' ? reference.streamEvents : reference.response}
                    maxHeight={woobeLayout.codeEditorMax}
                    actions={['copy', 'format']}
                  />
                </SectionBlock>

                {(reference.outputContract != null || reference.manifest?.length || reference.note || targetType === 'network') ? (
                  <SectionBlock title="Advanced" description="Deployment contracts and operational semantics." density="compact">
                    <div className="grid gap-ui-xs">
                      {reference.outputContract != null ? (
                        <DetailPanel title="Public output contract" description="Schema enforced when structured output is enabled.">
                          <JsonCodeBlock value={reference.outputContract} maxHeight={woobeLayout.codeStructuredDefault} actions={['copy', 'format']} />
                        </DetailPanel>
                      ) : null}

                      {reference.manifest && reference.manifest.length > 0 ? (
                        <DetailPanel title="Agent Release manifest" description="Immutable Agent Releases included in this Network deployment.">
                          <div className="grid gap-ui-xs sm:grid-cols-2">
                            {reference.manifest.map((item) => (
                              <TechnicalListItem
                                key={item.id}
                                label={item.name}
                                description={item.role || 'Agent Release'}
                                meta={item.id}
                                trailing={<Badge variant="outline" size="compact">{item.version}</Badge>}
                              />
                            ))}
                          </div>
                        </DetailPanel>
                      ) : null}

                      {reference.note ? (
                        <DetailPanel title="Runtime behavior" description="How the Runtime Key resolves releases and deployment changes.">
                          <p className="font-sans text-product-small leading-5 text-muted-foreground">{reference.note}</p>
                        </DetailPanel>
                      ) : null}

                      {targetType === 'network' ? (
                        <DetailPanel title="Network Run semantics" description="Relationship between the Network Run and delegated Agent Runs.">
                          <p className="font-sans text-product-small leading-5 text-muted-foreground">
                            Every request creates one Network Run. The public result belongs to the Network, while delegated Agent Runs remain attributable inside its Trace.
                          </p>
                        </DetailPanel>
                      ) : null}
                    </div>
                  </SectionBlock>
                ) : null}
              </div>
            </ScrollArea>
          </section>
        </div>
      </Dialog>

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
    </>
  )
}
