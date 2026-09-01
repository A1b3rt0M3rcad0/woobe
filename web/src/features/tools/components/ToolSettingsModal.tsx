import { useEffect, useState } from 'react'
import { Archive, Globe2, Server, ShieldCheck, Trash2, Wrench, X } from 'lucide-react'
import { toast } from 'sonner'

import { ResourcePill } from '@/components/common/OperationalResourceCard'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
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

function providerHost(tool: Tool): string {
  const config = (tool.config || {}) as HttpToolConfig & { server?: { url?: string } }
  const value = isMcpProviderTool(tool) ? config.server?.url : config.base_url || config.url
  if (!value) return 'Endpoint not recorded'
  try { return new URL(value).hostname } catch { return value }
}

function ImpactStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="border-r border-border/70 px-3 last:border-r-0">
      <p className="text-[10px] uppercase tracking-[0.12em] text-muted">{label}</p>
      <p className="mt-1 font-mono text-sm font-semibold text-white">{value}</p>
    </div>
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
      <div className="flex-1 space-y-5 p-5">
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

      <div className="sticky bottom-0 z-10 flex items-center justify-between gap-3 border-t border-border bg-surface/95 px-5 py-4 backdrop-blur">
        <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
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
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [usageImpact, setUsageImpact] = useState<ToolUsageImpact | null>(null)
  const [showLifecycleDialog, setShowLifecycleDialog] = useState(false)

  if (!tool) return null

  const retired = tool.status === 'deprecated'
  const groupedHttp = isGroupedHttpTool(tool)
  const mcp = isMcpProviderTool(tool)
  const protocol = protocolLabel(tool)
  const ToolIcon = mcp ? Server : groupedHttp ? Globe2 : Wrench

  const refreshParent = () => {
    void Promise.resolve(onSaved()).catch(() => undefined)
  }

  const saveStructuredTool = async (value: ApiFirstToolFormSubmitValue) => {
    if (retired) return
    try {
      await updateTool.mutateAsync({ toolId: tool.id, data: value })
      toast.success(`${mcp ? 'MCP Server' : 'HTTP API'} \"${value.name}\" updated`)
      onClose()
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
      onClose()
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

  return (
    <>
      <Dialog
        open
        onClose={onClose}
        title="Tool settings"
        className="max-h-[calc(100svh-2rem)] max-w-[900px] overflow-hidden"
        contentClassName="p-0"
      >
        <div className="grid h-[min(78svh,720px)] min-w-0 grid-rows-[auto_minmax(0,1fr)] overflow-hidden lg:grid-cols-[240px_minmax(0,1fr)] lg:grid-rows-1">
          <aside className="min-h-0 border-b border-border bg-background/20 lg:border-b-0 lg:border-r">
            <ScrollArea className="h-full">
              <div className="space-y-4 p-4">
                <section className="border-b border-border/70 pb-4">
                  <div className="flex items-start gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border/80 bg-surface/60 text-primary-light">
                      <ToolIcon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white">{tool.name}</p>
                      <p className="mt-1 truncate font-mono text-[10px] text-muted">{providerHost(tool)}</p>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <StatusBadge status={tool.status} size="compact" />
                    <ResourcePill>{protocol}</ResourcePill>
                    <ResourcePill tone={tool.risk_level === 'critical' || tool.risk_level === 'high' ? 'danger' : 'default'}>Risk · {tool.risk_level || 'unset'}</ResourcePill>
                  </div>
                </section>

                <section>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Configuration</p>
                  <p className="mt-2 text-xs leading-5 text-muted">
                    {groupedHttp
                      ? 'Edit the API domain, shared request settings and route contracts.'
                      : mcp
                        ? 'Edit Tool metadata here. Connection, discovery and permissions stay in the MCP capability controls.'
                        : 'Edit the legacy single-request HTTP configuration.'}
                  </p>
                </section>

                {projectControls && (isHttpProviderTool(tool) || mcp) ? (
                  <section className="border-t border-border/70 pt-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Capabilities</p>
                    <p className="mt-1 text-[11px] leading-4 text-muted">Review the globally available operations. Agent-specific exposure remains versioned inside each Agent Draft.</p>
                    {mcp ? <McpProviderPanel tool={tool} onChanged={onSaved} /> : <HttpProviderPanel tool={tool} />}
                  </section>
                ) : null}

                {projectControls ? (
                  <section className="border-t border-border/70 pt-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Runtime status</p>
                    <p className="mt-2 text-xs leading-5 text-muted">
                      {retired
                        ? 'Retired globally. Existing versioned usage remains preserved, but new Agent bindings are blocked.'
                        : 'Control whether this Tool is available for Agent bindings.'}
                    </p>
                    <Button className="mt-3 w-full" size="sm" variant="outline" onClick={handleToggleStatus} loading={busyAction === 'status' || updateStatus.isPending}>
                      {retired ? 'Reactivate Tool' : tool.status === 'active' ? 'Disable Tool' : 'Enable Tool'}
                    </Button>
                  </section>
                ) : null}

                {projectControls ? (
                  <section className="border-t border-red-500/20 pt-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-red-200">Lifecycle</p>
                    <p className="mt-2 text-xs leading-5 text-muted">Review Agent references before retiring or deleting this Tool.</p>
                    <Button className="mt-3 w-full" variant="destructive" size="sm" onClick={handleReviewRemoval} loading={busyAction === 'lifecycle'}>
                      <Trash2 className="mr-2 h-3.5 w-3.5" />Review removal
                    </Button>
                  </section>
                ) : null}
              </div>
            </ScrollArea>
          </aside>

          <section className="min-h-0 overflow-y-auto overscroll-contain bg-surface/40">
            {retired ? (
              <div className="border-b border-amber-400/15 bg-amber-400/5 px-5 py-3 text-xs text-amber-100">
                This Tool is retired and its configuration is read-only until it is reactivated.
              </div>
            ) : null}

            {groupedHttp ? (
              <div className={retired ? 'pointer-events-none select-none opacity-60' : ''}>
                <ApiFirstToolForm
                  initialTool={tool}
                  submitLabel="Save changes"
                  loading={updateTool.isPending}
                  onSubmit={saveStructuredTool}
                  onCancel={onClose}
                />
              </div>
            ) : mcp ? (
              <McpMetadataEditor
                tool={tool}
                onCancel={onClose}
                onSaved={() => { onClose(); refreshParent() }}
                disabled={retired}
              />
            ) : (
              <LegacyHttpEditor
                tool={tool}
                onCancel={onClose}
                onSaved={() => { onClose(); refreshParent() }}
                disabled={retired}
              />
            )}
          </section>
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
      <div className="flex-1 space-y-5 p-5">
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
      <div className="sticky bottom-0 z-10 flex items-center justify-between gap-3 border-t border-border bg-surface/95 px-5 py-4 backdrop-blur">
        <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
        <Button type="submit" disabled={disabled} loading={updateTool.isPending}>
          <ShieldCheck className="mr-2 h-4 w-4" />Save changes
        </Button>
      </div>
    </form>
  )
}
