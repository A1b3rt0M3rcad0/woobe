import { useEffect, useState, type ReactNode } from 'react'
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
  type LucideIcon,
} from 'lucide-react'
import { toast } from 'sonner'

import { ResourcePill } from '@/components/common/OperationalResourceCard'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { getToolUsageImpact, type ToolUsageImpact } from '@/features/tools/api'
import { ApiFirstToolForm, type ApiFirstToolFormSubmitValue } from '@/features/tools/components/ApiFirstToolForm'
import { HttpProviderPanel, isHttpProviderTool } from '@/features/tools/components/HttpProviderPanel'
import { McpProviderPanel, isMcpProviderTool } from '@/features/tools/components/McpProviderPanel'
import { inspectHttpToolContract, isHttpToolGroup } from '@/features/tools/httpToolContract'
import { useDeleteTool, useUpdateTool, useUpdateToolStatus } from '@/features/tools/hooks'
import type { HttpHeader, HttpToolConfig, Tool } from '@/features/tools/types'
import { cn } from '@/lib/utils'

interface ToolSettingsModalProps {
  tool: Tool | null
  onClose: () => void
  onSaved: () => void | Promise<void>
  projectControls?: boolean
}

type ToolSection = 'overview' | 'configuration' | 'capabilities' | 'runtime' | 'lifecycle'

type ToolSidebarItem = {
  id: ToolSection
  label: string
  icon: LucideIcon
  disabled?: boolean
}

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

function ImpactStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="border-r border-border/70 px-3 last:border-r-0">
      <p className="text-[10px] uppercase tracking-[0.12em] text-muted">{label}</p>
      <p className="mt-1 font-mono text-sm font-semibold text-white">{value}</p>
    </div>
  )
}

function SidebarSectionTitle({ children }: { children: string }) {
  return (
    <p className="hidden px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted/80 md:block">
      {children}
    </p>
  )
}

function SidebarNavButton({
  item,
  active,
  onClick,
}: {
  item: ToolSidebarItem
  active: boolean
  onClick: () => void
}) {
  const Icon = item.icon
  return (
    <button
      type="button"
      disabled={item.disabled}
      onClick={onClick}
      className={cn(
        'group flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-[border-color,background-color,color] md:w-full md:text-sm',
        item.disabled && 'cursor-not-allowed opacity-45',
        active
          ? 'border-primary/35 bg-primary/10 text-primary-light'
          : 'border-transparent text-muted hover:border-primary/20 hover:bg-background/70 hover:text-white',
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="whitespace-nowrap md:truncate">{item.label}</span>
    </button>
  )
}

function ReadOnlyField({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0 rounded-xl border border-border/80 bg-background/55 p-4">
      <p className="text-[11px] uppercase tracking-wider text-muted">{label}</p>
      <p className={cn('mt-1 break-words text-sm font-medium text-white', mono && 'font-mono text-xs')}>{value}</p>
    </div>
  )
}

function SectionCard({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <p className="mt-1 text-xs leading-5 text-muted">{description}</p>
      <div className="mt-5">{children}</div>
    </section>
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
    if (!name.trim()) {
      toast.error('Tool name is required')
      return
    }
    if (!url.trim()) {
      toast.error('URL is required')
      return
    }

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
    if (contract.errors.length) {
      toast.error(contract.errors[0])
      return
    }

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
      toast.success(`Tool \"${name.trim()}\" updated`)
      onSaved()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Tool')
    }
  }

  return (
    <form onSubmit={save} className="flex min-h-full flex-col">
      <div className="flex-1 space-y-5 p-5 lg:p-6">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary-light">Legacy HTTP</p>
          <h3 className="mt-1 text-base font-semibold text-white">Request configuration</h3>
          <p className="mt-1 text-xs leading-5 text-muted">Existing single-route Tools remain compatible. New HTTP APIs should use grouped routes.</p>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted">Name *</label>
            <Input disabled={disabled} value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted">Risk</label>
            <Select disabled={disabled} value={riskLevel} onChange={(event) => setRiskLevel(event.target.value)} options={RISK_LEVELS} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted">Description</label>
            <Input disabled={disabled} value={description} onChange={(event) => setDescription(event.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted">Timeout (ms)</label>
            <Input disabled={disabled} type="number" min={1000} max={120000} value={timeoutMs} onChange={(event) => setTimeoutMs(Number(event.target.value))} />
          </div>
        </div>

        <section className="space-y-4 border-t border-border/70 pt-5">
          <div className="grid gap-3 md:grid-cols-[130px_minmax(0,1fr)]">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">Method</label>
              <Select disabled={disabled} value={method} onChange={(event) => setMethod(event.target.value)} options={HTTP_METHODS} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">URL *</label>
              <Input disabled={disabled} value={url} onChange={(event) => setUrl(event.target.value)} className="font-mono text-xs" />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-white">Headers</p>
                <p className="mt-0.5 text-[11px] text-muted">Request headers applied to this route.</p>
              </div>
              <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={addHeader}>Add header</Button>
            </div>
            {headers.length === 0 ? <p className="text-xs text-muted">No headers configured.</p> : null}
            {headers.map((header) => (
              <div key={header.id} className="grid gap-2 sm:grid-cols-[1fr_1fr_32px]">
                <Input disabled={disabled} value={header.key} onChange={(event) => updateHeader(header.id, 'key', event.target.value)} placeholder="Name" />
                <Input disabled={disabled} value={header.value || ''} onChange={(event) => updateHeader(header.id, 'value', event.target.value)} placeholder="Value" />
                <Button type="button" size="sm" variant="ghost" disabled={disabled} className="text-red-300" onClick={() => removeHeader(header.id)} aria-label="Remove header">
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>

          {showBody ? (
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">Body</label>
              <Textarea disabled={disabled} value={body} onChange={(event) => setBody(event.target.value)} className="min-h-[140px] font-mono text-xs" />
            </div>
          ) : null}
        </section>
      </div>

      <div className="sticky bottom-0 z-10 flex items-center justify-between gap-3 border-t border-border bg-surface/95 px-5 py-4 backdrop-blur lg:px-6">
        <Button type="button" variant="outline" onClick={onCancel}>Close</Button>
        <Button type="submit" disabled={disabled} loading={updateTool.isPending}>
          <ShieldCheck className="mr-2 h-4 w-4" />Save changes
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
    if (!name.trim()) {
      toast.error('Tool name is required')
      return
    }
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
      toast.success(`Tool \"${name.trim()}\" updated`)
      onSaved()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Tool')
    }
  }

  return (
    <form onSubmit={save} className="flex min-h-full flex-col">
      <div className="flex-1 space-y-5 p-5 lg:p-6">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary-light">MCP Server</p>
          <h3 className="mt-1 text-base font-semibold text-white">Tool metadata</h3>
          <p className="mt-1 text-xs leading-5 text-muted">Connection, OAuth discovery and remote capabilities are managed through the MCP capability controls.</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted">Name *</label>
            <Input disabled={disabled} value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted">Risk</label>
            <Select disabled={disabled} value={riskLevel} onChange={(event) => setRiskLevel(event.target.value)} options={RISK_LEVELS} />
          </div>
          <div className="md:col-span-2">
            <label className="mb-1 block text-xs font-medium text-muted">Description</label>
            <Textarea disabled={disabled} value={description} onChange={(event) => setDescription(event.target.value)} className="min-h-[96px]" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted">Timeout (ms)</label>
            <Input disabled={disabled} type="number" min={1000} max={120000} value={timeoutMs} onChange={(event) => setTimeoutMs(Number(event.target.value))} />
          </div>
        </div>
      </div>
      <div className="sticky bottom-0 z-10 flex items-center justify-between gap-3 border-t border-border bg-surface/95 px-5 py-4 backdrop-blur lg:px-6">
        <Button type="button" variant="outline" onClick={onCancel}>Close</Button>
        <Button type="submit" disabled={disabled} loading={updateTool.isPending}>
          <ShieldCheck className="mr-2 h-4 w-4" />Save changes
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

  const configurationItems: ToolSidebarItem[] = [
    { id: 'overview', label: 'Overview', icon: Info },
    { id: 'configuration', label: 'Configuration', icon: Settings2 },
  ]
  const operationItems: ToolSidebarItem[] = projectControls
    ? [
        ...(hasCapabilityPanel ? [{ id: 'capabilities' as const, label: 'Capabilities', icon: Activity }] : []),
        { id: 'runtime', label: 'Runtime', icon: Gauge },
        { id: 'lifecycle', label: 'Lifecycle', icon: Archive },
      ]
    : []

  const refreshParent = () => {
    void Promise.resolve(onSaved()).catch(() => undefined)
  }

  const saveStructuredTool = async (value: ApiFirstToolFormSubmitValue) => {
    if (retired) return
    try {
      await updateTool.mutateAsync({ toolId: tool.id, data: value })
      toast.success(`${mcp ? 'MCP Server' : 'HTTP API'} \"${value.name}\" updated`)
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
    <div className="space-y-5">
      <SectionCard
        title="Tool identity"
        description="Project-level capability identity. Agent-specific exposure and permission overrides remain versioned inside each Agent Draft."
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <ReadOnlyField label="Name" value={tool.name} />
          <ReadOnlyField label="Protocol" value={protocol} />
          <ReadOnlyField label="Endpoint" value={providerEndpoint(tool)} mono />
          <ReadOnlyField label="Tool ID" value={tool.id} mono />
        </div>
        {tool.description ? (
          <div className="mt-4 rounded-xl border border-border/80 bg-background/55 p-4">
            <p className="text-[11px] uppercase tracking-wider text-muted">Description</p>
            <p className="mt-1 text-sm leading-6 text-slate-200">{tool.description}</p>
          </div>
        ) : null}
      </SectionCard>

      <SectionCard
        title="Operational state"
        description="A Tool belongs to the Project. Releases preserve the Tool snapshot referenced by the Agent version that was published."
      >
        <div className="flex flex-wrap gap-2">
          <StatusBadge status={tool.status} size="compact" />
          <ResourcePill>{protocol}</ResourcePill>
          <ResourcePill tone={tool.risk_level === 'critical' || tool.risk_level === 'high' ? 'danger' : 'default'}>
            Risk · {tool.risk_level || 'unset'}
          </ResourcePill>
          <ResourcePill>{tool.timeout_ms || 30000} ms timeout</ResourcePill>
        </div>
      </SectionCard>
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
    <div className="space-y-5">
      <SectionCard
        title="Available capabilities"
        description="Review the operations exposed by this Project Tool. Agent-specific Allow, Review or Deny decisions remain part of the Agent Draft and Release snapshot."
      >
        {mcp ? <McpProviderPanel tool={tool} onChanged={refreshParent} /> : <HttpProviderPanel tool={tool} />}
      </SectionCard>
    </div>
  ) : null

  const runtimeContent = projectControls ? (
    <div className="space-y-5">
      <SectionCard
        title="Runtime availability"
        description="Control whether this Project Tool is available for new Agent bindings. Existing immutable releases retain their snapshot semantics."
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={tool.status} size="compact" />
              <span className="font-mono text-xs text-muted">{providerHost(tool)}</span>
            </div>
            <p className="mt-2 max-w-xl text-xs leading-5 text-muted">
              {retired
                ? 'This Tool is retired. Reactivation makes it available for new bindings again.'
                : tool.status === 'active'
                  ? 'The Tool is available for Project-level binding and runtime resolution.'
                  : 'The Tool is disabled for new runtime usage until re-enabled.'}
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            className="shrink-0"
            onClick={handleToggleStatus}
            loading={busyAction === 'status' || updateStatus.isPending}
          >
            {retired ? 'Reactivate Tool' : tool.status === 'active' ? 'Disable Tool' : 'Enable Tool'}
          </Button>
        </div>
      </SectionCard>
    </div>
  ) : null

  const lifecycleContent = projectControls ? (
    <div className="space-y-5">
      <SectionCard
        title="Lifecycle"
        description="Removal is evaluated against Agent Draft, Staging, Production and historical Release references before any destructive action is allowed."
      >
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
          <p className="text-sm font-medium text-white">Retire or delete this Tool</p>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-muted">
            Retirement blocks new bindings while preserving immutable references. Permanent deletion is only available when no Agent version references the Tool.
          </p>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            className="mt-4"
            onClick={handleReviewRemoval}
            loading={busyAction === 'lifecycle'}
          >
            <Trash2 className="mr-2 h-3.5 w-3.5" />Review removal
          </Button>
        </div>
      </SectionCard>
    </div>
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
  const configurationOwnsFooter = activeSection === 'configuration'

  return (
    <>
      <Dialog
        open
        onClose={onClose}
        title="Tool settings"
        className="flex h-[min(900px,calc(100svh-2rem))] max-w-7xl flex-col overflow-hidden"
        contentClassName="min-h-0 flex-1 p-0"
      >
        <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)] md:grid-cols-[230px_minmax(0,1fr)] md:grid-rows-1">
          <aside className="flex min-h-0 min-w-0 flex-col border-b border-border bg-background/35 md:border-b-0 md:border-r">
            <div className="hidden border-b border-border p-4 md:block">
              <div className="flex min-w-0 items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light">
                  <ToolIcon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 items-center gap-2">
                    <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-white">{tool.name}</h3>
                    <StatusBadge status={tool.status} size="compact" />
                  </div>
                  <p className="mt-1 truncate text-xs text-muted">{protocol}</p>
                  <button
                    type="button"
                    className="mt-2 flex max-w-full items-center gap-1.5 font-mono text-[11px] text-muted hover:text-white"
                    onClick={() => {
                      void navigator.clipboard.writeText(providerEndpoint(tool))
                      toast.success('Tool endpoint copied')
                    }}
                  >
                    <span className="truncate">{providerHost(tool)}</span>
                    <Copy className="h-3 w-3 shrink-0" />
                  </button>
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-border/70 pt-3 text-[11px] text-muted">
                <span>Risk · {tool.risk_level || 'unset'}</span>
                <span className="font-mono" title={tool.id}>{shortId(tool.id)}</span>
              </div>
            </div>

            <nav className="flex min-w-0 gap-1 overflow-x-auto p-2 md:block md:flex-1 md:space-y-5 md:overflow-y-auto md:p-3">
              <div className="contents md:block md:space-y-2">
                <SidebarSectionTitle>Configuration</SidebarSectionTitle>
                <div className="contents md:block md:space-y-1">
                  {configurationItems.map((item) => (
                    <SidebarNavButton
                      key={item.id}
                      item={item}
                      active={activeSection === item.id}
                      onClick={() => setActiveSection(item.id)}
                    />
                  ))}
                </div>
              </div>

              {operationItems.length > 0 ? (
                <div className="contents md:block md:space-y-2">
                  <SidebarSectionTitle>Operate</SidebarSectionTitle>
                  <div className="contents md:block md:space-y-1">
                    {operationItems.map((item) => (
                      <SidebarNavButton
                        key={item.id}
                        item={item}
                        active={activeSection === item.id}
                        onClick={() => setActiveSection(item.id)}
                      />
                    ))}
                  </div>
                </div>
              ) : null}
            </nav>
          </aside>

          <main className="flex min-h-0 min-w-0 flex-col overflow-hidden">
            {retired ? (
              <div className="shrink-0 border-b border-amber-400/15 bg-amber-400/5 px-5 py-3 text-xs text-amber-100 lg:px-6">
                This Tool is retired. Configuration is read-only until it is reactivated.
              </div>
            ) : null}

            <div className={cn(
              'min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain',
              configurationOwnsFooter ? 'p-0' : 'p-4 sm:p-5 lg:p-6',
            )}>
              {currentContent}
            </div>

            {!configurationOwnsFooter ? (
              <div className="flex shrink-0 flex-col-reverse gap-2 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur sm:flex-row sm:items-center sm:justify-between lg:px-6">
                <p className="text-[11px] text-muted">
                  Project Tool · {protocol} · {tool.status}
                </p>
                <Button type="button" variant="outline" onClick={onClose}>Close</Button>
              </div>
            ) : null}
          </main>
        </div>
      </Dialog>

      <Dialog open={showLifecycleDialog && Boolean(usageImpact)} onClose={closeLifecycleDialog} title={lifecycleTitle} className="max-w-2xl">
        {usageImpact ? (
          <div className="space-y-5">
            <div>
              <p className="text-sm font-medium text-white">{tool.name}</p>
              <p className="mt-2 text-sm leading-6 text-muted">
                {usageImpact.can_delete
                  ? 'No Agent version references this Tool. Permanent deletion is available and cannot be undone.'
                  : usageImpact.can_retire
                    ? 'This Tool is referenced by Agent versions. Retiring it prevents new Agent bindings while preserving existing Draft, Staging, Production and historical Release snapshots.'
                    : 'This Tool is already retired and still referenced. Remove it from every Agent version before permanent deletion becomes available.'}
              </p>
            </div>

            <div className="grid grid-cols-2 divide-x divide-border/70 rounded-lg border border-border/80 bg-background/40 py-3 md:grid-cols-4">
              <ImpactStat label="Draft" value={usageImpact.draft_agents} />
              <ImpactStat label="Staging" value={usageImpact.staging_agents} />
              <ImpactStat label="Production" value={usageImpact.production_agents} />
              <ImpactStat label="History" value={usageImpact.historical_releases} />
            </div>

            <p className="text-xs text-muted">Total version references: <span className="font-mono text-white">{usageImpact.total_references}</span></p>

            <div className="flex items-center justify-between gap-3 border-t border-border pt-4">
              <Button variant="outline" onClick={closeLifecycleDialog}>Cancel</Button>
              {usageImpact.can_delete ? (
                <Button variant="destructive" onClick={handleConfirmLifecycle} loading={busyAction === 'lifecycle-confirm' || deleteTool.isPending}>
                  <Trash2 className="mr-2 h-4 w-4" />Delete permanently
                </Button>
              ) : usageImpact.can_retire ? (
                <Button onClick={handleConfirmLifecycle} loading={busyAction === 'lifecycle-confirm' || updateStatus.isPending}>
                  <Archive className="mr-2 h-4 w-4" />Retire Tool
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
      </Dialog>
    </>
  )
}
