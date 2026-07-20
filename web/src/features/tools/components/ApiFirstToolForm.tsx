import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Globe2, Plus, Route, Server, X } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { HttpRequestBodyEditor } from '@/features/tools/components/HttpRequestBodyEditor'
import { inspectHttpRouteContract, inspectHttpToolContract, isHttpToolGroup } from '@/features/tools/httpToolContract'
import type {
  CreateToolRequest,
  HttpHeader,
  HttpRouteConfig,
  HttpToolConfig,
  McpToolConfig,
  Tool,
  ToolConfig,
  ToolProtocol,
} from '@/features/tools/types'
import { toast } from 'sonner'

export type ApiFirstToolFormSubmitValue = Omit<CreateToolRequest, 'project_id'>

type Protocol = 'http' | 'mcp'
type HeaderDraft = { id: string; key: string; value: string; sensitive?: boolean }
type RouteDraft = Omit<HttpRouteConfig, 'headers' | 'body'> & {
  headers: HeaderDraft[]
  body: string
}

interface ApiFirstToolFormProps {
  submitLabel?: string
  cancelLabel?: string
  loading?: boolean
  initialTool?: Tool | null
  onSubmit: (value: ApiFirstToolFormSubmitValue) => Promise<void>
  onCancel: () => void
}

const PROTOCOLS = [
  { value: 'http', label: 'HTTP API' },
  { value: 'mcp', label: 'MCP Server' },
]

const METHODS = [
  { value: 'GET', label: 'GET' },
  { value: 'POST', label: 'POST' },
  { value: 'PUT', label: 'PUT' },
  { value: 'PATCH', label: 'PATCH' },
  { value: 'DELETE', label: 'DELETE' },
  { value: 'HEAD', label: 'HEAD' },
]

const RISKS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
]

const ROUTE_STATUSES = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
]

const PERMISSIONS = [
  { value: 'review', label: 'Review by default' },
  { value: 'allow', label: 'Allowed by default' },
  { value: 'deny', label: 'Denied by default' },
]

let nextLocalId = 1
function localId(prefix: string): string {
  nextLocalId += 1
  return `${prefix}_${Date.now()}_${nextLocalId}`
}

function stableRouteId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return localId('route')
}

function headerDraft(header?: HttpHeader): HeaderDraft {
  return {
    id: localId('header'),
    key: header?.key || '',
    value: header?.value || '',
    sensitive: header?.sensitive,
  }
}

function normalizeHeaders(headers: HeaderDraft[]): HttpHeader[] {
  return headers
    .map((header) => ({
      key: header.key.trim(),
      value: header.value,
      ...(header.sensitive !== undefined ? { sensitive: header.sensitive } : {}),
    }))
    .filter((header) => header.key.length > 0)
}

function bodyToText(body: HttpRouteConfig['body']): string {
  if (body == null) return ''
  return typeof body === 'string' ? body : JSON.stringify(body, null, 2)
}

function operationId(value: string): string {
  const normalized = value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return normalized && !/^\d/.test(normalized) ? normalized : `route_${normalized || 'operation'}`
}

function defaultRoute(index = 1, riskLevel = 'low'): RouteDraft {
  return {
    id: stableRouteId(),
    operation_id: `route_${index}`,
    name: `Route ${index}`,
    description: '',
    method: 'GET',
    path: '/',
    headers: [],
    body: '',
    variables: {},
    input_schema: undefined,
    output_schema: undefined,
    risk_level: riskLevel,
    status: 'active',
    default_permission: 'review',
  }
}

function routeFromConfig(route: HttpRouteConfig, index: number): RouteDraft {
  return {
    ...route,
    id: route.id || stableRouteId(),
    operation_id: route.operation_id || `route_${index + 1}`,
    name: route.name || `Route ${index + 1}`,
    description: route.description || '',
    method: route.method || 'GET',
    path: route.path || '/',
    headers: (route.headers || []).map((header) => headerDraft(header)),
    body: bodyToText(route.body),
    risk_level: route.risk_level || 'low',
    status: route.status || 'active',
    default_permission: route.default_permission || 'review',
  }
}

function initialHttpConfig(tool?: Tool | null): HttpToolConfig | null {
  if (!tool) return null
  const config = (tool.config || {}) as HttpToolConfig
  return isHttpToolGroup(config) ? config : null
}

function serverName(value: string): string {
  try {
    return `MCP ${new URL(value).hostname}`
  } catch {
    return 'MCP Server'
  }
}

function groupName(value: string): string {
  try {
    return new URL(value).hostname
  } catch {
    return 'HTTP API'
  }
}

function HeadersEditor({
  title,
  headers,
  onChange,
}: {
  title: string
  headers: HeaderDraft[]
  onChange: (headers: HeaderDraft[]) => void
}) {
  const addHeader = () => onChange([...headers, headerDraft()])
  const updateHeader = (id: string, field: 'key' | 'value', value: string) => {
    onChange(headers.map((header) => header.id === id ? { ...header, [field]: value } : header))
  }
  const removeHeader = (id: string) => onChange(headers.filter((header) => header.id !== id))

  return (
    <div className="space-y-2 rounded-xl border border-border/80 bg-background/45 p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">{title}</p>
        <Button type="button" size="sm" variant="ghost" onClick={addHeader}>
          <Plus className="mr-1 h-3 w-3" />
          Add header
        </Button>
      </div>
      {headers.length === 0 ? <p className="text-xs italic text-muted">No headers configured.</p> : null}
      {headers.map((header) => (
        <div key={header.id} className="grid gap-2 md:grid-cols-[minmax(120px,0.8fr)_minmax(180px,1.2fr)_32px]">
          <Input value={header.key} onChange={(event) => updateHeader(header.id, 'key', event.target.value)} placeholder="Header name" />
          <Input value={header.value} onChange={(event) => updateHeader(header.id, 'value', event.target.value)} placeholder="Value or {{secret:name}}" className="font-mono text-xs" />
          <Button type="button" size="sm" variant="ghost" className="text-red-300" onClick={() => removeHeader(header.id)}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      ))}
    </div>
  )
}

export function ApiFirstToolForm({
  submitLabel = 'Create',
  cancelLabel = 'Cancel',
  loading = false,
  initialTool = null,
  onSubmit,
  onCancel,
}: ApiFirstToolFormProps) {
  const initialHttp = initialHttpConfig(initialTool)
  const initialMcp = initialTool?.type === 'mcp' ? (initialTool.config || {}) as McpToolConfig : null
  const initialProtocol: Protocol = initialMcp ? 'mcp' : 'http'

  const [protocol, setProtocol] = useState<Protocol>(initialProtocol)
  const [name, setName] = useState(initialTool?.name || '')
  const [description, setDescription] = useState(initialTool?.description || '')
  const [riskLevel, setRiskLevel] = useState(initialTool?.risk_level || 'low')
  const [timeoutMs, setTimeoutMs] = useState(initialTool?.timeout_ms || initialHttp?.timeout_ms || initialMcp?.timeout_ms || 30000)
  const [baseUrl, setBaseUrl] = useState(initialHttp?.base_url || '')
  const [sharedHeaders, setSharedHeaders] = useState<HeaderDraft[]>((initialHttp?.headers || []).map((header) => headerDraft(header)))
  const [routes, setRoutes] = useState<RouteDraft[]>(
    initialHttp?.routes?.length
      ? initialHttp.routes.map(routeFromConfig)
      : [defaultRoute(1, initialTool?.risk_level || 'low')],
  )
  const [activeRouteId, setActiveRouteId] = useState(routes[0]?.id || '')
  const [mcpUrl, setMcpUrl] = useState(initialMcp?.server?.url || '')
  const [mcpHeaders, setMcpHeaders] = useState<HeaderDraft[]>((initialMcp?.server?.headers || []).map((header) => headerDraft(header)))

  const activeRoute = routes.find((route) => route.id === activeRouteId) || routes[0]
  const activeRouteIndex = Math.max(0, routes.findIndex((route) => route.id === activeRoute?.id))

  const groupConfigPreview = useMemo<HttpToolConfig>(() => ({
    protocol: 'http',
    mode: 'group',
    schema_version: 2,
    base_url: baseUrl.trim(),
    headers: normalizeHeaders(sharedHeaders),
    timeout_ms: timeoutMs,
    routes: routes.map((route) => ({
      ...route,
      headers: normalizeHeaders(route.headers),
      body: route.body || undefined,
    })),
  }), [baseUrl, routes, sharedHeaders, timeoutMs])

  const routeContract = activeRoute
    ? inspectHttpRouteContract(groupConfigPreview, {
      ...activeRoute,
      headers: normalizeHeaders(activeRoute.headers),
      body: activeRoute.body || undefined,
    })
    : null

  const updateRoute = (routeId: string, patch: Partial<RouteDraft>) => {
    setRoutes((current) => current.map((route) => route.id === routeId ? { ...route, ...patch } : route))
  }

  const addRoute = () => {
    const route = defaultRoute(routes.length + 1, riskLevel)
    setRoutes((current) => [...current, route])
    setActiveRouteId(route.id)
  }

  const removeRoute = (routeId: string) => {
    if (routes.length === 1) {
      toast.error('HTTP API group requires at least one route.')
      return
    }
    const next = routes.filter((route) => route.id !== routeId)
    setRoutes(next)
    if (activeRouteId === routeId) setActiveRouteId(next[0]?.id || '')
  }

  const normalizeRoute = (route: RouteDraft): HttpRouteConfig => {
    const routeHeaders = normalizeHeaders(route.headers)
    const canHaveBody = !['GET', 'HEAD'].includes(route.method)
    const hasContentType = [...normalizeHeaders(sharedHeaders), ...routeHeaders]
      .some((header) => header.key.toLowerCase() === 'content-type')
    if (canHaveBody && route.body.trim() && !hasContentType) {
      routeHeaders.push({ key: 'Content-Type', value: 'application/json' })
    }
    const preview = inspectHttpRouteContract(
      { ...groupConfigPreview, headers: normalizeHeaders(sharedHeaders) },
      { ...route, headers: routeHeaders, body: canHaveBody && route.body.trim() ? route.body.trim() : undefined },
    )
    return {
      id: route.id,
      operation_id: route.operation_id.trim(),
      name: route.name.trim(),
      description: route.description.trim(),
      method: route.method,
      path: route.path.trim(),
      headers: routeHeaders,
      body: canHaveBody && route.body.trim() ? route.body.trim() : undefined,
      variables: route.variables || {},
      input_schema: preview.inputSchema,
      output_schema: route.output_schema,
      risk_level: route.risk_level || riskLevel,
      status: route.status || 'active',
      default_permission: route.default_permission || 'review',
      permission: route.permission,
      timeout_ms: route.timeout_ms,
    }
  }

  const buildConfig = (): ToolConfig => {
    if (protocol === 'mcp') {
      return {
        protocol: 'mcp',
        mode: 'server',
        exposure: 'all_discovered',
        server: {
          transport: 'streamable_http',
          url: mcpUrl.trim(),
          headers: normalizeHeaders(mcpHeaders),
        },
        discovered_tools: initialMcp?.discovered_tools || [],
        discovery_cache_ttl_seconds: 3600,
        timeout_ms: timeoutMs,
      } satisfies McpToolConfig
    }
    return {
      protocol: 'http',
      mode: 'group',
      schema_version: 2,
      base_url: baseUrl.trim().replace(/\/+$/, ''),
      headers: normalizeHeaders(sharedHeaders),
      routes: routes.map(normalizeRoute),
      timeout_ms: timeoutMs,
    } satisfies HttpToolConfig
  }

  const validate = (): string | null => {
    if (protocol === 'mcp') {
      if (!mcpUrl.trim()) return 'MCP server URL is required'
      try { new URL(mcpUrl.trim()) } catch { return 'MCP server URL is invalid' }
      return null
    }

    if (!description.trim()) return 'HTTP API group description is required'
    if (!baseUrl.trim()) return 'HTTP API base URL is required'
    try {
      const parsed = new URL(baseUrl.trim())
      if (!['http:', 'https:'].includes(parsed.protocol)) return 'HTTP API base URL must use HTTP or HTTPS'
      if (parsed.search || parsed.hash) return 'HTTP API base URL cannot contain query parameters or fragments'
    } catch {
      return 'HTTP API base URL is invalid'
    }
    if (routes.length === 0) return 'At least one HTTP route is required'
    const operationIds = new Set<string>()
    for (const route of routes) {
      if (!route.name.trim()) return 'Every HTTP route requires a name'
      if (!route.description.trim()) return `Route "${route.name || 'Unnamed'}" requires a description`
      if (!route.path.trim()) return `Route "${route.name}" requires a relative path`
      if (/^https?:\/\//i.test(route.path.trim())) return `Route "${route.name}" path must be relative to the base URL`
      if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(route.operation_id.trim())) return `Route "${route.name}" has an invalid operation ID`
      if (operationIds.has(route.operation_id.trim())) return `Operation ID "${route.operation_id}" is duplicated`
      operationIds.add(route.operation_id.trim())
      const preview = inspectHttpRouteContract(groupConfigPreview, {
        ...route,
        headers: normalizeHeaders(route.headers),
        body: route.body || undefined,
      })
      if (preview.errors.length) return `${route.name}: ${preview.errors[0]}`
    }
    return null
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const error = validate()
    if (error) {
      toast.error(error)
      return
    }
    const config = buildConfig()
    const contract = protocol === 'http' ? inspectHttpToolContract(config as HttpToolConfig) : null
    if (contract?.errors.length) {
      toast.error(contract.errors[0])
      return
    }
    const resolvedName = name.trim() || (protocol === 'mcp' ? serverName(mcpUrl.trim()) : groupName(baseUrl.trim()))
    await onSubmit({
      name: resolvedName,
      description: description.trim() || (protocol === 'mcp'
        ? 'MCP provider. Woobe loads public tools automatically and identifies authentication requirements.'
        : undefined),
      type: protocol as ToolProtocol,
      config,
      input_schema: contract?.inputSchema,
      risk_level: riskLevel,
      timeout_ms: timeoutMs,
    })
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      {!initialTool ? (
        <div className="grid gap-3 md:grid-cols-2">
          {PROTOCOLS.map((item) => {
            const active = protocol === item.value
            const Icon = item.value === 'http' ? Globe2 : Server
            return (
              <button
                key={item.value}
                type="button"
                onClick={() => setProtocol(item.value as Protocol)}
                className={`rounded-xl border p-4 text-left transition-colors ${active ? 'border-primary/50 bg-primary/10' : 'border-border/80 bg-background/40 hover:bg-background/70'}`}
              >
                <Icon className="h-4 w-4 text-primary-light" />
                <p className="mt-3 text-sm font-semibold text-white">{item.label}</p>
                <p className="mt-1 text-xs leading-5 text-muted">{item.value === 'http' ? 'Group several routes from one API domain.' : 'Connect a remote MCP server and discover tools.'}</p>
              </button>
            )
          })}
        </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_160px_160px]">
        <div><label className="mb-1 block text-xs font-medium text-muted">Display name</label><Input value={name} onChange={(event) => setName(event.target.value)} placeholder={protocol === 'mcp' ? 'Auto-filled from URL' : 'Portal da Transparência'} /></div>
        <div><label className="mb-1 block text-xs font-medium text-muted">Default risk</label><Select value={riskLevel} onChange={(event) => setRiskLevel(event.target.value)} options={RISKS} /></div>
        <div><label className="mb-1 block text-xs font-medium text-muted">Timeout (ms)</label><Input type="number" value={timeoutMs} min={1000} max={120000} onChange={(event) => setTimeoutMs(Number(event.target.value))} /></div>
      </div>

      <div><label className="mb-1 block text-xs font-medium text-muted">Description {protocol === 'http' ? '*' : ''}</label><Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder={protocol === 'http' ? 'Explain what this API group provides so Agents understand its domain.' : 'What this MCP provider does'} className="min-h-[72px]" /></div>

      {protocol === 'http' ? (
        <div className="grid min-h-[560px] overflow-hidden rounded-2xl border border-border/80 bg-card/40 lg:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="space-y-4 border-b border-border/80 p-4 lg:border-b-0 lg:border-r">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">Base URL *</label>
              <Input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" className="font-mono text-xs" />
              <p className="mt-1 text-[10px] leading-4 text-muted">All routes must remain under this domain and base path.</p>
            </div>
            <HeadersEditor title="Shared headers" headers={sharedHeaders} onChange={setSharedHeaders} />
            <div className="rounded-xl border border-border/80 bg-background/45 p-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold text-white">Routes</p>
                  <p className="mt-0.5 text-[10px] text-muted">{routes.length} configured</p>
                </div>
                <Button type="button" size="sm" variant="outline" onClick={addRoute}><Plus className="mr-1 h-3 w-3" />Add</Button>
              </div>
              <div className="mt-3 space-y-2">
                {routes.map((route, index) => (
                  <button
                    key={route.id}
                    type="button"
                    onClick={() => setActiveRouteId(route.id)}
                    className={`w-full rounded-lg border p-2 text-left transition-colors ${route.id === activeRoute?.id ? 'border-primary/45 bg-primary/10' : 'border-border/70 bg-surface/50 hover:bg-surface'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="rounded bg-background px-1.5 py-0.5 font-mono text-[9px] font-semibold text-primary-light">{route.method}</span>
                      <span className="text-[9px] text-muted">#{index + 1}</span>
                    </div>
                    <p className="mt-2 truncate text-xs font-medium text-white">{route.name || 'Unnamed route'}</p>
                    <p className="mt-1 truncate font-mono text-[10px] text-muted">{route.path || '/'}</p>
                  </button>
                ))}
              </div>
            </div>
          </aside>

          {activeRoute ? (
            <section className="min-w-0 space-y-4 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2"><Route className="h-4 w-4 text-primary-light" /><h3 className="text-sm font-semibold text-white">Route {activeRouteIndex + 1}</h3></div>
                  <p className="mt-1 text-xs text-muted">Each route becomes an independent function available to the Agent.</p>
                </div>
                <Button type="button" size="sm" variant="ghost" className="text-red-300" onClick={() => removeRoute(activeRoute.id)}><X className="mr-1 h-3.5 w-3.5" />Remove</Button>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <div><label className="mb-1 block text-xs font-medium text-muted">Route name *</label><Input value={activeRoute.name} onChange={(event) => updateRoute(activeRoute.id, { name: event.target.value, operation_id: activeRoute.operation_id.startsWith('route_') ? operationId(event.target.value) : activeRoute.operation_id })} placeholder="Search employees" /></div>
                <div><label className="mb-1 block text-xs font-medium text-muted">Operation ID *</label><Input value={activeRoute.operation_id} onChange={(event) => updateRoute(activeRoute.id, { operation_id: operationId(event.target.value) })} placeholder="search_employees" className="font-mono text-xs" /></div>
              </div>
              <div><label className="mb-1 block text-xs font-medium text-muted">Route description *</label><Textarea value={activeRoute.description} onChange={(event) => updateRoute(activeRoute.id, { description: event.target.value })} placeholder="Explain exactly when the Agent should call this route." className="min-h-[72px]" /></div>
              <div className="grid gap-3 md:grid-cols-[130px_minmax(0,1fr)]">
                <div><label className="mb-1 block text-xs font-medium text-muted">Method</label><Select value={activeRoute.method} onChange={(event) => updateRoute(activeRoute.id, { method: event.target.value })} options={METHODS} /></div>
                <div><label className="mb-1 block text-xs font-medium text-muted">Relative path *</label><Input value={activeRoute.path} onChange={(event) => updateRoute(activeRoute.id, { path: event.target.value })} placeholder="/employees/{{employee_id}}" className="font-mono text-xs" /></div>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <div><label className="mb-1 block text-xs font-medium text-muted">Route risk</label><Select value={activeRoute.risk_level || riskLevel} onChange={(event) => updateRoute(activeRoute.id, { risk_level: event.target.value })} options={RISKS} /></div>
                <div><label className="mb-1 block text-xs font-medium text-muted">Status</label><Select value={activeRoute.status || 'active'} onChange={(event) => updateRoute(activeRoute.id, { status: event.target.value })} options={ROUTE_STATUSES} /></div>
                <div><label className="mb-1 block text-xs font-medium text-muted">Default permission</label><Select value={activeRoute.default_permission || 'review'} onChange={(event) => updateRoute(activeRoute.id, { default_permission: event.target.value as 'allow' | 'review' | 'deny' })} options={PERMISSIONS} /></div>
              </div>
              <HeadersEditor title="Route headers" headers={activeRoute.headers} onChange={(headers) => updateRoute(activeRoute.id, { headers })} />

              {!['GET', 'HEAD'].includes(activeRoute.method) ? (
                <HttpRequestBodyEditor value={activeRoute.body} onChange={(body) => updateRoute(activeRoute.id, { body })} />
              ) : null}

              <div className="rounded-xl border border-border/80 bg-background/45 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Detected Agent inputs</p>
                {routeContract?.parameterNames.length ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {routeContract.parameterNames.map((parameter) => <span key={parameter} className="rounded-md border border-border bg-surface px-2 py-1 font-mono text-[10px] text-white">{parameter}</span>)}
                  </div>
                ) : <p className="mt-2 text-xs text-muted">No {'{{parameter}}'} placeholders detected.</p>}
              </div>
            </section>
          ) : null}
        </div>
      ) : (
        <div className="space-y-4 rounded-2xl border border-border/80 bg-card/40 p-4">
          <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-3 text-xs leading-5 text-muted">Woobe loads public MCP tools after creation and classifies OAuth, credentials and provider-managed connection requirements.</div>
          <div><label className="mb-1 block text-xs font-medium text-muted">MCP Server URL *</label><Input value={mcpUrl} onChange={(event) => setMcpUrl(event.target.value)} placeholder="https://mcp.example.com/mcp" className="font-mono text-xs" /></div>
          <HeadersEditor title="Connection headers" headers={mcpHeaders} onChange={setMcpHeaders} />
        </div>
      )}

      <div className="flex flex-col justify-end gap-2 border-t border-border pt-4 sm:flex-row">
        <Button type="button" variant="outline" onClick={onCancel}>{cancelLabel}</Button>
        <Button type="submit" loading={loading}>{submitLabel}</Button>
      </div>
    </form>
  )
}
