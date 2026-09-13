import { useEffect, useState } from 'react'
import {
  Activity,
  Archive,
  Copy,
  Gauge,
  Globe2,
  Info,
  Server,
  Settings2,
  ShieldCheck,
  Trash2,
  Wrench,
  X,
} from 'lucide-react'
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Dialog,
  Field,
  FieldDescription,
  FieldLabel,
  Input,
  MetricTile,
  SectionBlock,
  SegmentedControl,
  Select,
  TechnicalListItem,
  Textarea,
} from '@woobe/ui'
import { toast } from 'sonner'

import { StatusBadge } from '@/components/common/StatusBadge'
import { getToolUsageImpact, type ToolUsageImpact } from '@/features/tools/api'
import { ApiFirstToolForm, type ApiFirstToolFormSubmitValue } from '@/features/tools/components/ApiFirstToolForm'
import { HttpProviderPanel, isHttpProviderTool } from '@/features/tools/components/HttpProviderPanel'
import { McpProviderPanel, isMcpProviderTool } from '@/features/tools/components/McpProviderPanel'
import { inspectHttpToolContract, isHttpToolGroup } from '@/features/tools/httpToolContract'
import { useDeleteTool, useUpdateTool, useUpdateToolStatus } from '@/features/tools/hooks'
import type { HttpHeader, HttpToolConfig, Tool } from '@/features/tools/types'

interface ToolSettingsModalProps {
  tool: Tool | null
  onClose: () => void
  onSaved: () => void | Promise<void>
  projectControls?: boolean
}

type ToolSection = 'overview' | 'configuration' | 'capabilities' | 'runtime' | 'lifecycle'

const HTTP_METHODS = [
  { value: 'GET', label: 'GET' },
  { value: 'POST', label: 'POST' },
  { value: 'PUT', label: 'PUT' },
  { value: 'PATCH', label: 'PATCH' },
  { value: 'DELETE', label: 'DELETE' },
  { value: 'HEAD', label: 'HEAD' },
]

const RISK_LEVELS = [
  { value: 'low', label: 'Low risk' },
  { value: 'medium', label: 'Medium risk' },
  { value: 'high', label: 'High risk' },
  { value: 'critical', label: 'Critical risk' },
]

let nextHeaderId = 1
function headerId() {
  nextHeaderId += 1
  return `header_${nextHeaderId}`
}

type HeaderDraft = HttpHeader & { id: string }

function isGroupedHttpTool(tool: Tool | null): tool is Tool {
  if (!tool || isMcpProviderTool(tool)) return false
  return isHttpToolGroup((tool.config || {}) as HttpToolConfig)
}

function protocolLabel(tool: Tool): string {
  if (isMcpProviderTool(tool)) return 'MCP Server'
  if (isGroupedHttpTool(tool)) return 'HTTP API'
  return 'Legacy HTTP Tool'
}

function providerEndpoint(tool: Tool): string {
  const config = (tool.config || {}) as HttpToolConfig & { server?: { url?: string } }
  return isMcpProviderTool(tool)
    ? config.server?.url || 'Endpoint not recorded'
    : config.base_url || config.url || 'Endpoint not recorded'
}

function providerHost(tool: Tool): string {
  const value = providerEndpoint(tool)
  if (value === 'Endpoint not recorded') return value
  try { return new URL(value).hostname } catch { return value }
}

function shortId(value: string): string {
  return value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value
}

function ReadOnlyField({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <TechnicalListItem
      label={label}
      description={value}
      title={value}
      className={mono ? '[&>span:nth-child(2)>span:nth-child(2)]:font-mono' : undefined}
    />
  )
}

function LegacyHttpEditor({
  tool,
  onCancel,
  onSaved,
  disabled,
}: {
  tool: Tool
  onCancel: () => void
  onSaved: () => void
  disabled: boolean
}) {
  const updateTool = useUpdateTool()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [riskLevel, setRiskLevel] = useState('low')
  const [timeoutMs, setTimeoutMs] = useState(30000)
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('')
  const [body, setBody] = useState('')
  const [headers, setHeaders] = useState<HeaderDraft[]>([])

  useEffect(() => {
    setName(tool.name)
    setDescription(tool.description || '')
    setRiskLevel(tool.risk_level || 'low')
    setTimeoutMs(tool.timeout_ms || 30000)
    const config = (tool.config || {}) as HttpToolConfig
    setMethod(config.method || 'GET')
    setUrl(config.url || '')
    setBody(typeof config.body === 'string' ? config.body : config.body ? JSON.stringify(config.body, null, 2) : '')
    setHeaders((config.headers || []).map((header) => ({ ...header, id: headerId() })))
  }, [tool])

  const showBody = !['GET', 'HEAD'].includes(method)
  const addHeader = () => setHeaders((current) => [...current, { id: headerId(), key: '', value: '' }])
  const updateHeader = (id: string, field: 'key' | 'value', value: string) => {
    setHeaders((current) => current.map((header) => header.id === id ? { ...header, [field]: value } : header))
  }
  const removeHeader = (id: string) => setHeaders((current) => current.filter((header) => header.id !== id))

  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    if (disabled) return
    if (!name.trim()) return void toast.error('Tool name is required')
    if (!url.trim()) return void toast.error('URL is required')

    const config: HttpToolConfig = {
      protocol: 'http',
      mode: 'single',
      method,
      url: url.trim(),
      headers: headers
        .filter((header) => header.key.trim())
        .map(({ id: _id, ...header }) => ({ ...header, key: header.key.trim() })),
      ...(showBody && body.trim() ? { body: body.trim() } : {}),
      timeout_ms: timeoutMs,
    }
    const contract = inspectHttpToolContract(config, tool.input_schema)
    if (contract.errors.length) return void toast.error(contract.errors[0])

    try {
      await updateTool.mutateAsync({
        toolId: tool.id,
        data: {
          name: name.trim(),
          description: description.trim() || undefined,
          risk_level: riskLevel,
          timeout_ms: timeoutMs,
          type: 'http',
          config,
          input_schema: contract.inputSchema,
        },
      })
      toast.success(`Tool "${name.trim()}" updated`)
      onSaved()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Tool')
    }
  }

  return (
    <form onSubmit={save} className="grid gap-ui-md">
      <SectionBlock
        eyebrow="Legacy HTTP"
        title="Request configuration"
        description="Existing single-route Tools remain compatible. New HTTP APIs should use grouped routes."
      >
        <div className="grid gap-ui-md md:grid-cols-2">
          <Field>
            <FieldLabel>Name *</FieldLabel>
            <Input disabled={disabled} value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>Risk</FieldLabel>
            <Select disabled={disabled} value={riskLevel} onChange={(event) => setRiskLevel(event.target.value)} options={RISK_LEVELS} />
          </Field>
          <Field>
            <FieldLabel>Description</FieldLabel>
            <Input disabled={disabled} value={description} onChange={(event) => setDescription(event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>Timeout (ms)</FieldLabel>
            <Input disabled={disabled} type="number" min={1000} max={120000} value={timeoutMs} onChange={(event) => setTimeoutMs(Number(event.target.value))} />
          </Field>
        </div>
      </SectionBlock>

      <SectionBlock title="HTTP request" description="Single-route request definition retained for backward compatibility.">
        <div className="grid gap-ui-md">
          <div className="grid gap-ui-md md:grid-cols-[8rem_minmax(0,1fr)]">
            <Field>
              <FieldLabel>Method</FieldLabel>
              <Select disabled={disabled} value={method} onChange={(event) => setMethod(event.target.value)} options={HTTP_METHODS} />
            </Field>
            <Field>
              <FieldLabel>URL *</FieldLabel>
              <Input disabled={disabled} value={url} onChange={(event) => setUrl(event.target.value)} className="font-mono" />
            </Field>
          </div>

          <Field>
            <div className="flex items-center justify-between gap-ui-sm">
              <div>
                <FieldLabel>Headers</FieldLabel>
                <FieldDescription>Request headers applied to this route.</FieldDescription>
              </div>
              <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={addHeader}>Add header</Button>
            </div>
            {headers.length === 0 ? <p className="font-sans text-product-caption text-muted-foreground">No headers configured.</p> : null}
            <div className="grid gap-ui-xs">
              {headers.map((header) => (
                <div key={header.id} className="grid gap-ui-xs sm:grid-cols-[1fr_1fr_auto]">
                  <Input disabled={disabled} value={header.key} onChange={(event) => updateHeader(header.id, 'key', event.target.value)} placeholder="Name" />
                  <Input disabled={disabled} value={header.value || ''} onChange={(event) => updateHeader(header.id, 'value', event.target.value)} placeholder="Value" />
                  <Button type="button" size="iconSm" variant="ghost" disabled={disabled} onClick={() => removeHeader(header.id)} aria-label="Remove header">
                    <X className="h-icon w-icon text-error" />
                  </Button>
                </div>
              ))}
            </div>
          </Field>

          {showBody ? (
            <Field>
              <FieldLabel>Body</FieldLabel>
              <Textarea disabled={disabled} value={body} onChange={(event) => setBody(event.target.value)} className="min-h-multiline font-mono" />
            </Field>
          ) : null}
        </div>
      </SectionBlock>

      <div className="flex items-center justify-between gap-ui-sm border-t border-border pt-ui-md">
        <Button type="button" variant="outline" onClick={onCancel}>Close</Button>
        <Button type="submit" disabled={disabled} loading={updateTool.isPending}>
          <ShieldCheck className="mr-ui-sm h-icon w-icon" />Save changes
        </Button>
      </div>
    </form>
  )
}

function McpMetadataEditor({
  tool,
  onCancel,
  onSaved,
  disabled,
}: {
  tool: Tool
  onCancel: () => void
  onSaved: () => void
  disabled: boolean
}) {
  const updateTool = useUpdateTool()
  const [name, setName] = useState(tool.name)
  const [description, setDescription] = useState(tool.description || '')
  const [riskLevel, setRiskLevel] = useState(tool.risk_level || 'low')
  const [timeoutMs, setTimeoutMs] = useState(tool.timeout_ms || 30000)

  useEffect(() => {
    setName(tool.name)
    setDescription(tool.description || '')
    setRiskLevel(tool.risk_level || 'low')
    setTimeoutMs(tool.timeout_ms || 30000)
  }, [tool])

  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    if (disabled) return
    if (!name.trim()) return void toast.error('Tool name is required')
    try {
      await updateTool.mutateAsync({
        toolId: tool.id,
        data: {
          name: name.trim(),
          description: description.trim() || undefined,
          risk_level: riskLevel,
          timeout_ms: timeoutMs,
        },
      })
      toast.success(`Tool "${name.trim()}" updated`)
      onSaved()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Tool')
    }
  }

  return (
    <form onSubmit={save} className="grid gap-ui-md">
      <SectionBlock
        eyebrow="MCP Server"
        title="Tool metadata"
        description="Connection, OAuth discovery and remote capabilities are managed through the MCP capability controls."
      >
        <div className="grid gap-ui-md md:grid-cols-2">
          <Field>
            <FieldLabel>Name *</FieldLabel>
            <Input disabled={disabled} value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>Risk</FieldLabel>
            <Select disabled={disabled} value={riskLevel} onChange={(event) => setRiskLevel(event.target.value)} options={RISK_LEVELS} />
          </Field>
          <Field className="md:col-span-2">
            <FieldLabel>Description</FieldLabel>
            <Textarea disabled={disabled} value={description} onChange={(event) => setDescription(event.target.value)} className="min-h-multiline" />
          </Field>
          <Field>
            <FieldLabel>Timeout (ms)</FieldLabel>
            <Input disabled={disabled} type="number" min={1000} max={120000} value={timeoutMs} onChange={(event) => setTimeoutMs(Number(event.target.value))} />
          </Field>
        </div>
      </SectionBlock>

      <div className="flex items-center justify-between gap-ui-sm border-t border-border pt-ui-md">
        <Button type="button" variant="outline" onClick={onCancel}>Close</Button>
        <Button type="submit" disabled={disabled} loading={updateTool.isPending}>
          <ShieldCheck className="mr-ui-sm h-icon w-icon" />Save changes
        </Button>
      </div>
    </form>
  )
}

export function ToolSettingsModal({ tool, onClose, onSaved, projectControls = false }: ToolSettingsModalProps) {
  const updateTool = useUpdateTool()
  const updateStatus = useUpdateToolStatus()
  const deleteTool = useDeleteTool()
  const [activeSection, setActiveSection] = useState<ToolSection>('overview')
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [usageImpact, setUsageImpact] = useState<ToolUsageImpact | null>(null)
  const [showLifecycleDialog, setShowLifecycleDialog] = useState(false)

  useEffect(() => {
    setActiveSection('overview')
    setUsageImpact(null)
    setShowLifecycleDialog(false)
  }, [tool?.id])

  if (!tool) return null

  const retired = tool.status === 'deprecated'
  const groupedHttp = isGroupedHttpTool(tool)
  const mcp = isMcpProviderTool(tool)
  const protocol = protocolLabel(tool)
  const ToolIcon = mcp ? Server : groupedHttp ? Globe2 : Wrench
  const hasCapabilityPanel = projectControls && (isHttpProviderTool(tool) || mcp)

  const navigationItems = [
    { value: 'overview', label: 'Overview', icon: <Info className="h-icon-sm w-icon-sm" /> },
    { value: 'configuration', label: 'Configuration', icon: <Settings2 className="h-icon-sm w-icon-sm" /> },
    ...(hasCapabilityPanel ? [{ value: 'capabilities', label: 'Capabilities', icon: <Activity className="h-icon-sm w-icon-sm" /> }] : []),
    ...(projectControls ? [
      { value: 'runtime', label: 'Runtime', icon: <Gauge className="h-icon-sm w-icon-sm" /> },
      { value: 'lifecycle', label: 'Lifecycle', icon: <Archive className="h-icon-sm w-icon-sm" /> },
    ] : []),
  ]

  const refreshParent = () => {
    void Promise.resolve(onSaved()).catch(() => undefined)
  }

  const saveStructuredTool = async (value: ApiFirstToolFormSubmitValue) => {
    if (retired) return
    try {
      await updateTool.mutateAsync({ toolId: tool.id, data: value })
      toast.success(`${mcp ? 'MCP Server' : 'HTTP API'} "${value.name}" updated`)
      refreshParent()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Tool')
    }
  }

  const handleToggleStatus = async () => {
    const nextStatus = retired ? 'active' : tool.status === 'active' ? 'inactive' : 'active'
    try {
      setBusyAction('status')
      await updateStatus.mutateAsync({ toolId: tool.id, data: { status: nextStatus } })
      toast.success(retired ? 'Tool reactivated' : nextStatus === 'active' ? 'Tool enabled' : 'Tool disabled')
      refreshParent()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Tool status')
    } finally {
      setBusyAction(null)
    }
  }

  const handleReviewRemoval = async () => {
    try {
      setBusyAction('lifecycle')
      const impact = await getToolUsageImpact(tool.id)
      setUsageImpact(impact)
      setShowLifecycleDialog(true)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to inspect Tool usage')
    } finally {
      setBusyAction(null)
    }
  }

  const handleConfirmLifecycle = async () => {
    if (!usageImpact) return
    try {
      setBusyAction('lifecycle-confirm')
      if (usageImpact.can_delete) {
        await deleteTool.mutateAsync(tool.id)
        toast.success('Tool deleted permanently')
      } else if (usageImpact.can_retire) {
        await updateStatus.mutateAsync({ toolId: tool.id, data: { status: 'deprecated' } })
        toast.success('Tool retired. Existing Agent versions were preserved.')
      } else {
        return
      }
      setShowLifecycleDialog(false)
      setUsageImpact(null)
      if (usageImpact.can_delete) onClose()
      refreshParent()
    } catch (error) {
      try {
        const latestImpact = await getToolUsageImpact(tool.id)
        setUsageImpact(latestImpact)
      } catch {
        // Keep the original lifecycle failure as the user-facing error.
      }
      toast.error(error instanceof Error ? error.message : 'Failed to update Tool lifecycle')
    } finally {
      setBusyAction(null)
    }
  }

  const closeLifecycleDialog = () => {
    setShowLifecycleDialog(false)
    setUsageImpact(null)
  }

  const lifecycleTitle = usageImpact?.can_delete
    ? 'Delete Tool permanently'
    : usageImpact?.can_retire
      ? 'Retire Tool'
      : 'Tool is still in use'

  const overviewContent = (
    <div className="grid gap-ui-md">
      <SectionBlock
        title="Tool identity"
        description="Project-level capability identity. Agent-specific exposure and permission overrides remain versioned inside each Agent Draft."
      >
        <div className="grid gap-ui-xs sm:grid-cols-2">
          <ReadOnlyField label="Name" value={tool.name} />
          <ReadOnlyField label="Protocol" value={protocol} />
          <ReadOnlyField label="Endpoint" value={providerEndpoint(tool)} mono />
          <ReadOnlyField label="Tool ID" value={tool.id} mono />
        </div>
        {tool.description ? (
          <div className="mt-ui-md border-t border-border pt-ui-md">
            <p className="font-sans text-product-small leading-5 text-muted-foreground">{tool.description}</p>
          </div>
        ) : null}
      </SectionBlock>

      <SectionBlock
        title="Operational state"
        description="A Tool belongs to the Project. Releases preserve the Tool snapshot referenced by the Agent version that was published."
        density="compact"
      >
        <div className="flex flex-wrap gap-ui-sm">
          <StatusBadge status={tool.status} size="compact" />
          <Badge variant="outline" size="compact">{protocol}</Badge>
          <Badge variant={tool.risk_level === 'critical' || tool.risk_level === 'high' ? 'destructive' : 'outline'} size="compact">
            Risk · {tool.risk_level || 'unset'}
          </Badge>
          <Badge variant="outline" size="compact">{tool.timeout_ms || 30000} ms timeout</Badge>
        </div>
      </SectionBlock>
    </div>
  )

  const configurationContent = groupedHttp ? (
    <div className={retired ? 'pointer-events-none select-none opacity-60' : ''}>
      <ApiFirstToolForm
        initialTool={tool}
        submitLabel="Save changes"
        cancelLabel="Close"
        loading={updateTool.isPending}
        onSubmit={saveStructuredTool}
        onCancel={onClose}
      />
    </div>
  ) : mcp ? (
    <McpMetadataEditor tool={tool} onCancel={onClose} onSaved={refreshParent} disabled={retired} />
  ) : (
    <LegacyHttpEditor tool={tool} onCancel={onClose} onSaved={refreshParent} disabled={retired} />
  )

  const capabilitiesContent = hasCapabilityPanel ? (
    <SectionBlock
      title="Available capabilities"
      description="Review the operations exposed by this Project Tool. Agent-specific Allow, Review or Deny decisions remain part of the Agent Draft and Release snapshot."
    >
      {mcp ? <McpProviderPanel tool={tool} onChanged={refreshParent} /> : <HttpProviderPanel tool={tool} />}
    </SectionBlock>
  ) : null

  const runtimeContent = projectControls ? (
    <SectionBlock
      title="Runtime availability"
      description="Control whether this Project Tool is available for new Agent bindings. Existing immutable releases retain their snapshot semantics."
    >
      <div className="flex flex-col gap-ui-md sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-ui-sm">
            <StatusBadge status={tool.status} size="compact" />
            <span className="truncate font-mono text-system-label text-muted-foreground">{providerHost(tool)}</span>
          </div>
          <p className="mt-ui-sm max-w-xl font-sans text-product-small leading-5 text-muted-foreground">
            {retired
              ? 'This Tool is retired. Reactivation makes it available for new bindings again.'
              : tool.status === 'active'
                ? 'The Tool is available for Project-level binding and runtime resolution.'
                : 'The Tool is disabled for new runtime usage until re-enabled.'}
          </p>
        </div>
        <Button type="button" variant="outline" className="shrink-0" onClick={handleToggleStatus} loading={busyAction === 'status' || updateStatus.isPending}>
          {retired ? 'Reactivate Tool' : tool.status === 'active' ? 'Disable Tool' : 'Enable Tool'}
        </Button>
      </div>
    </SectionBlock>
  ) : null

  const lifecycleContent = projectControls ? (
    <SectionBlock
      title="Lifecycle"
      description="Removal is evaluated against Agent Draft, Staging, Production and historical Release references before any destructive action is allowed."
    >
      <Alert variant="destructive">
        <AlertTitle>Retire or delete this Tool</AlertTitle>
        <AlertDescription>
          Retirement blocks new bindings while preserving immutable references. Permanent deletion is only available when no Agent version references the Tool.
        </AlertDescription>
        <Button type="button" variant="destructive" size="sm" className="mt-ui-md" onClick={handleReviewRemoval} loading={busyAction === 'lifecycle'}>
          <Trash2 className="mr-ui-sm h-icon w-icon" />Review removal
        </Button>
      </Alert>
    </SectionBlock>
  ) : null

  const currentContent = activeSection === 'overview'
    ? overviewContent
    : activeSection === 'configuration'
      ? configurationContent
      : activeSection === 'capabilities'
        ? capabilitiesContent
        : activeSection === 'runtime'
          ? runtimeContent
          : lifecycleContent

  return (
    <>
      <Dialog
        open
        onClose={onClose}
        title="Tool settings"
        className="flex max-h-dialog max-w-dialog-wide flex-col overflow-hidden"
        contentClassName="min-h-0 flex-1 p-0"
      >
        <div className="flex h-full min-h-0 min-w-0 flex-col">
          <div className="shrink-0 border-b border-border bg-background/20 px-ui-lg py-ui-md">
            <div className="flex min-w-0 items-start gap-ui-md">
              <span className="flex h-control-nav w-control-nav shrink-0 items-center justify-center rounded-control border border-primary/25 bg-primary/[0.08] text-primary-light">
                <ToolIcon className="h-icon w-icon" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 flex-wrap items-center gap-ui-sm">
                  <h3 className="min-w-0 flex-1 truncate font-mono text-system-heading font-semibold text-accent-foreground">{tool.name}</h3>
                  <StatusBadge status={tool.status} size="compact" />
                </div>
                <div className="mt-ui-xs flex min-w-0 flex-wrap items-center gap-x-ui-md gap-y-ui-xs font-mono text-system-meta text-muted-foreground">
                  <span>{protocol}</span>
                  <span>Risk · {tool.risk_level || 'unset'}</span>
                  <span title={tool.id}>{shortId(tool.id)}</span>
                </div>
                <button
                  type="button"
                  className="mt-ui-xs flex max-w-full items-center gap-ui-xs font-mono text-system-meta text-muted-foreground transition-colors hover:text-accent-foreground"
                  onClick={() => {
                    void navigator.clipboard.writeText(providerEndpoint(tool))
                    toast.success('Tool endpoint copied')
                  }}
                >
                  <span className="truncate">{providerHost(tool)}</span>
                  <Copy className="h-icon-sm w-icon-sm shrink-0" />
                </button>
              </div>
            </div>

            <div className="mt-ui-md max-w-full overflow-x-auto">
              <SegmentedControl
                items={navigationItems}
                value={activeSection}
                onValueChange={(value) => setActiveSection(value as ToolSection)}
                ariaLabel="Tool settings sections"
                size="compact"
              />
            </div>
          </div>

          {retired ? (
            <div className="shrink-0 border-b border-border px-ui-lg py-ui-sm">
              <Alert variant="warning">
                <AlertDescription>This Tool is retired. Configuration is read-only until it is reactivated.</AlertDescription>
              </Alert>
            </div>
          ) : null}

          <main className="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain p-ui-lg lg:p-ui-xl">
            {currentContent}
          </main>

          {activeSection !== 'configuration' ? (
            <div className="flex shrink-0 flex-col-reverse gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md backdrop-blur sm:flex-row sm:items-center sm:justify-between lg:px-ui-xl">
              <p className="font-sans text-product-caption text-muted-foreground">Project Tool · {protocol} · {tool.status}</p>
              <Button type="button" variant="outline" onClick={onClose}>Close</Button>
            </div>
          ) : null}
        </div>
      </Dialog>

      <Dialog
        open={showLifecycleDialog && Boolean(usageImpact)}
        onClose={closeLifecycleDialog}
        title={lifecycleTitle}
        className="max-w-dialog"
        layer="nestedModal"
      >
        {usageImpact ? (
          <div className="grid gap-ui-md">
            <Alert variant={usageImpact.can_delete ? 'destructive' : 'warning'}>
              <AlertTitle>{tool.name}</AlertTitle>
              <AlertDescription>
                {usageImpact.can_delete
                  ? 'No Agent version references this Tool. Permanent deletion is available and cannot be undone.'
                  : usageImpact.can_retire
                    ? 'This Tool is referenced by Agent versions. Retiring it prevents new Agent bindings while preserving existing Draft, Staging, Production and historical Release snapshots.'
                    : 'This Tool is already retired and still referenced. Remove it from every Agent version before permanent deletion becomes available.'}
              </AlertDescription>
            </Alert>

            <div className="grid gap-ui-xs sm:grid-cols-2 lg:grid-cols-4">
              <MetricTile label="Draft" value={usageImpact.draft_agents} />
              <MetricTile label="Staging" value={usageImpact.staging_agents} />
              <MetricTile label="Production" value={usageImpact.production_agents} />
              <MetricTile label="History" value={usageImpact.historical_releases} />
            </div>

            <TechnicalListItem label="Total version references" description={String(usageImpact.total_references)} />

            <div className="flex items-center justify-between gap-ui-sm border-t border-border pt-ui-md">
              <Button variant="outline" onClick={closeLifecycleDialog}>Cancel</Button>
              {usageImpact.can_delete ? (
                <Button variant="destructive" onClick={handleConfirmLifecycle} loading={busyAction === 'lifecycle-confirm' || deleteTool.isPending}>
                  <Trash2 className="mr-ui-sm h-icon w-icon" />Delete permanently
                </Button>
              ) : usageImpact.can_retire ? (
                <Button onClick={handleConfirmLifecycle} loading={busyAction === 'lifecycle-confirm' || updateStatus.isPending}>
                  <Archive className="mr-ui-sm h-icon w-icon" />Retire Tool
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
      </Dialog>
    </>
  )
}
