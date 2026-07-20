import { useMemo, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { ArrowLeft, ChevronDown, Globe2, Plus, Route, Server, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

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

export type ApiFirstToolFormSubmitValue = Omit<CreateToolRequest, 'project_id'>

type Protocol = 'http' | 'mcp'
type FormStep = 'type' | 'details' | 'route'
type HeaderDraft = { id: string; key: string; value: string; sensitive?: boolean }
type RouteDraft = Omit<HttpRouteConfig, 'headers' | 'body'> & {
  headers: HeaderDraft[]
  body: string
}

interface RouteEditorState {
  draft: RouteDraft
  isNew: boolean
}

interface ApiFirstToolFormProps {
  submitLabel?: string
  cancelLabel?: string
  loading?: boolean
  initialTool?: Tool | null
  onSubmit: (value: ApiFirstToolFormSubmitValue) => Promise<void>
  onCancel: () => void
}

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

function defaultRoute(index = 1): RouteDraft {
  return {
    id: stableRouteId(),
    operation_id: `route_${index}`,
    name: '',
    description: '',
    method: 'GET',
    path: '/',
    headers: [],
    body: '',
    variables: {},
    input_schema: undefined,
    output_schema: undefined,
    risk_level: 'low',
    status: 'active',
    default_permission: 'review',
  }
}

function routeFromConfig(route: HttpRouteConfig, index: number): RouteDraft {
  return {
    ...route,
    id: route.id || stableRouteId(),
    operation_id: route.operation_id || `route_${index + 1}`,
    name: route.name || '',
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
  try { return `MCP ${new URL(value).hostname}` } catch { return '' }
}

function groupName(value: string): string {
  try { return new URL(value).hostname } catch { return '' }
}

function riskScore(risk?: string | null): number {
  const normalized = String(risk || '').toLowerCase()
  if (normalized === 'critical') return 4
  if (normalized === 'high') return 3
  if (normalized === 'medium') return 2
  return 1
}

function highestRouteRisk(routes: RouteDraft[]): string {
  return routes
    .filter((route) => route.status !== 'inactive')
    .reduce((highest, route) => riskScore(route.risk_level) > riskScore(highest) ? String(route.risk_level) : highest, 'low')
}

function FieldError({ message }: { message?: string }) {
  return message ? <p className="mt-1 text-[11px] text-red-300">{message}</p> : null
}

function AdvancedSection({
  open,
  onToggle,
  label = 'Advanced settings',
  children,
}: {
  open: boolean
  onToggle: () => void
  label?: string
  children: ReactNode
}) {
  return (
    <div className="rounded-xl border border-border/80 bg-background/30">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
        aria-expanded={open}
      >
        <span className="text-sm font-medium text-white">{label}</span>
        <ChevronDown className={`h-4 w-4 text-muted transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open ? <div className="space-y-4 border-t border-border/70 px-4 py-4">{children}</div> : null}
    </div>
  )
}

function HeadersEditor({
  headers,
  onChange,
}: {
  headers: HeaderDraft[]
  onChange: (headers: HeaderDraft[]) => void
}) {
  const addHeader = () => onChange([...headers, headerDraft()])
  const updateHeader = (id: string, field: 'key' | 'value', value: string) => {
    onChange(headers.map((header) => header.id === id ? { ...header, [field]: value } : header))
  }
  const removeHeader = (id: string) => onChange(headers.filter((header) => header.id !== id))

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-white">Headers</p>
          <p className="mt-0.5 text-[11px] text-muted">Use a secret reference for sensitive values.</p>
        </div>
        <Button type="button" size="sm" variant="ghost" onClick={addHeader}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          Add header
        </Button>
      </div>
      {headers.length === 0 ? <p className="text-xs text-muted">No headers configured.</p> : null}
      {headers.map((header) => (
        <div key={header.id} className="grid gap-2 sm:grid-cols-[minmax(120px,0.8fr)_minmax(180px,1.2fr)_32px]">
          <Input value={header.key} onChange={(event) => updateHeader(header.id, 'key', event.target.value)} placeholder="Header name" />
          <Input value={header.value} onChange={(event) => updateHeader(header.id, 'value', event.target.value)} placeholder="Value or {{secret:name}}" className="font-mono text-xs" />
          <Button type="button" size="sm" variant="ghost" className="text-red-300" onClick={() => removeHeader(header.id)} aria-label="Remove header">
            <Trash2 className="h-3.5 w-3.5" />
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

  const [step, setStep] = useState<FormStep>(initialTool ? 'details' : 'type')
  const [protocol, setProtocol] = useState<Protocol>(initialProtocol)
  const [name, setName] = useState(initialTool?.name || '')
  const [nameTouched, setNameTouched] = useState(Boolean(initialTool?.name))
  const [description, setDescription] = useState(initialTool?.description || '')
  const [timeoutMs, setTimeoutMs] = useState(initialTool?.timeout_ms || initialHttp?.timeout_ms || initialMcp?.timeout_ms || 30000)
  const [baseUrl, setBaseUrl] = useState(initialHttp?.base_url || '')
  const [sharedHeaders, setSharedHeaders] = useState<HeaderDraft[]>((initialHttp?.headers || []).map((header) => headerDraft(header)))
  const [routes, setRoutes] = useState<RouteDraft[]>(initialHttp?.routes?.map(routeFromConfig) || [])
  const [mcpUrl, setMcpUrl] = useState(initialMcp?.server?.url || '')
  const [mcpHeaders, setMcpHeaders] = useState<HeaderDraft[]>((initialMcp?.server?.headers || []).map((header) => headerDraft(header)))
  const [detailsAdvancedOpen, setDetailsAdvancedOpen] = useState(false)
  const [routeAdvancedOpen, setRouteAdvancedOpen] = useState(false)
  const [routeEditor, setRouteEditor] = useState<RouteEditorState | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [routeErrors, setRouteErrors] = useState<Record<string, string>>({})

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

  const routeContract = useMemo(() => {
    if (!routeEditor) return null
    return inspectHttpRouteContract(groupConfigPreview, {
      ...routeEditor.draft,
      headers: normalizeHeaders(routeEditor.draft.headers),
      body: routeEditor.draft.body || undefined,
    })
  }, [groupConfigPreview, routeEditor])

  const updateBaseUrl = (value: string) => {
    setBaseUrl(value)
    if (!nameTouched) setName(groupName(value))
    setErrors((current) => ({ ...current, baseUrl: '' }))
  }

  const updateMcpUrl = (value: string) => {
    setMcpUrl(value)
    if (!nameTouched) setName(serverName(value))
    setErrors((current) => ({ ...current, mcpUrl: '' }))
  }

  const selectProtocol = (nextProtocol: Protocol) => {
    setProtocol(nextProtocol)
    setName('')
    setNameTouched(false)
    setDescription('')
    setErrors({})
    setStep('details')
  }

  const editRoute = (route: RouteDraft) => {
    setRouteEditor({
      draft: {
        ...route,
        headers: route.headers.map((header) => headerDraft(header)),
      },
      isNew: false,
    })
    setRouteErrors({})
    setRouteAdvancedOpen(false)
    setStep('route')
  }

  const addRoute = () => {
    setRouteEditor({ draft: defaultRoute(routes.length + 1), isNew: true })
    setRouteErrors({})
    setRouteAdvancedOpen(false)
    setStep('route')
  }

  const removeRoute = (routeId: string) => {
    setRoutes((current) => current.filter((route) => route.id !== routeId))
  }

  const updateRouteDraft = (patch: Partial<RouteDraft>) => {
    setRouteEditor((current) => current ? { ...current, draft: { ...current.draft, ...patch } } : current)
  }

  const validateRoute = (route: RouteDraft): boolean => {
    const nextErrors: Record<string, string> = {}
    const resolvedOperationId = operationId(route.operation_id || route.name)
    if (!route.path.trim()) nextErrors.path = 'Relative path is required.'
    else if (/^https?:\/\//i.test(route.path.trim())) nextErrors.path = 'Use a path relative to the Base URL.'
    if (!route.name.trim()) nextErrors.name = 'Route name is required.'
    if (!route.description.trim()) nextErrors.description = 'Describe when the Agent should use this route.'
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(resolvedOperationId)) nextErrors.operationId = 'Operation ID is invalid.'
    const duplicate = routes.some((item) => item.id !== route.id && item.operation_id === resolvedOperationId)
    if (duplicate) nextErrors.operationId = 'Operation ID is already used by another route.'
    if (!['GET', 'HEAD'].includes(route.method) && route.body.trim()) {
      try { JSON.parse(route.body) } catch { nextErrors.body = 'Request body must be valid JSON.' }
    }
    const preview = inspectHttpRouteContract(groupConfigPreview, {
      ...route,
      operation_id: resolvedOperationId,
      headers: normalizeHeaders(route.headers),
      body: route.body || undefined,
    })
    if (preview.errors.length && !nextErrors.body) nextErrors.body = preview.errors[0]
    setRouteErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const saveRoute = () => {
    if (!routeEditor) return
    const draft = {
      ...routeEditor.draft,
      operation_id: operationId(routeEditor.draft.operation_id || routeEditor.draft.name),
      status: routeEditor.draft.status || 'active',
      default_permission: routeEditor.draft.default_permission || 'review',
    }
    if (!validateRoute(draft)) return
    setRoutes((current) => routeEditor.isNew
      ? [...current, draft]
      : current.map((route) => route.id === draft.id ? draft : route))
    setRouteEditor(null)
    setRouteErrors({})
    setStep('details')
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
      operation_id: operationId(route.operation_id || route.name),
      name: route.name.trim(),
      description: route.description.trim(),
      method: route.method,
      path: route.path.trim(),
      headers: routeHeaders,
      body: canHaveBody && route.body.trim() ? route.body.trim() : undefined,
      variables: route.variables || {},
      input_schema: preview.inputSchema,
      output_schema: route.output_schema,
      risk_level: route.risk_level || 'low',
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

  const validateDetails = (): boolean => {
    const nextErrors: Record<string, string> = {}
    if (protocol === 'mcp') {
      if (!mcpUrl.trim()) nextErrors.mcpUrl = 'MCP Server URL is required.'
      else {
        try {
          const parsed = new URL(mcpUrl.trim())
          if (!['http:', 'https:'].includes(parsed.protocol)) nextErrors.mcpUrl = 'Use an HTTP or HTTPS URL.'
        } catch { nextErrors.mcpUrl = 'Enter a valid MCP Server URL.' }
      }
      if (!name.trim()) nextErrors.name = 'Display name is required.'
    } else {
      if (!baseUrl.trim()) nextErrors.baseUrl = 'Base URL is required.'
      else {
        try {
          const parsed = new URL(baseUrl.trim())
          if (!['http:', 'https:'].includes(parsed.protocol)) nextErrors.baseUrl = 'Use an HTTP or HTTPS URL.'
          else if (parsed.search || parsed.hash) nextErrors.baseUrl = 'Base URL cannot contain query parameters or fragments.'
        } catch { nextErrors.baseUrl = 'Enter a valid Base URL.' }
      }
      if (!name.trim()) nextErrors.name = 'Display name is required.'
      if (!description.trim()) nextErrors.description = 'Describe what this API provides to Agents.'
      if (routes.length === 0) nextErrors.routes = 'Add at least one route.'
    }
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const submitDetails = async () => {
    if (!validateDetails()) return
    const config = buildConfig()
    const contract = protocol === 'http' ? inspectHttpToolContract(config as HttpToolConfig) : null
    if (contract?.errors.length) {
      toast.error(contract.errors[0])
      return
    }
    await onSubmit({
      name: name.trim(),
      description: description.trim() || (protocol === 'mcp'
        ? 'MCP provider. Woobe loads public tools automatically and identifies authentication requirements.'
        : undefined),
      type: protocol as ToolProtocol,
      config,
      input_schema: contract?.inputSchema,
      risk_level: protocol === 'http' ? highestRouteRisk(routes) : initialTool?.risk_level || 'low',
      timeout_ms: timeoutMs,
    })
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (step === 'route') {
      saveRoute()
      return
    }
    if (step === 'details') await submitDetails()
  }

  const cancelCurrentStep = () => {
    if (step === 'route') {
      setRouteEditor(null)
      setRouteErrors({})
      setStep('details')
      return
    }
    onCancel()
  }

  const primaryDisabled = step === 'route'
    ? !routeEditor?.draft.name.trim() || !routeEditor.draft.description.trim() || !routeEditor.draft.path.trim()
    : protocol === 'http'
      ? !baseUrl.trim() || !name.trim() || !description.trim() || routes.length === 0
      : !mcpUrl.trim() || !name.trim()

  const primaryLabel = step === 'route'
    ? 'Save route'
    : initialTool
      ? 'Save changes'
      : protocol === 'mcp'
        ? 'Create & discover'
        : submitLabel === 'Create' ? 'Create API' : submitLabel

  return (
    <form onSubmit={submit} className="min-h-full">
      <div className="space-y-5 p-6">
        {step === 'type' ? (
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-semibold text-white">What are you connecting?</h3>
              <p className="mt-1 text-sm text-muted">Choose a provider type. Configuration appears only after selection.</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <button type="button" onClick={() => selectProtocol('http')} className="rounded-xl border border-border/80 bg-background/35 p-4 text-left transition-colors hover:border-primary/45 hover:bg-primary/5">
                <Globe2 className="h-4 w-4 text-primary-light" />
                <p className="mt-3 text-sm font-semibold text-white">HTTP API</p>
                <p className="mt-1 text-xs leading-5 text-muted">Connect one API domain and expose its routes.</p>
              </button>
              <button type="button" onClick={() => selectProtocol('mcp')} className="rounded-xl border border-border/80 bg-background/35 p-4 text-left transition-colors hover:border-primary/45 hover:bg-primary/5">
                <Server className="h-4 w-4 text-primary-light" />
                <p className="mt-3 text-sm font-semibold text-white">MCP Server</p>
                <p className="mt-1 text-xs leading-5 text-muted">Connect a remote server and discover its tools.</p>
              </button>
            </div>
          </div>
        ) : null}

        {step === 'details' ? (
          <div className="space-y-5">
            <div className="flex items-start gap-3">
              {!initialTool ? (
                <Button type="button" size="sm" variant="ghost" className="mt-0.5 px-2" onClick={() => setStep('type')}>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              ) : null}
              <div>
                <h3 className="text-base font-semibold text-white">{protocol === 'http' ? (initialTool ? 'Edit HTTP API' : 'Create HTTP API') : 'Connect MCP Server'}</h3>
                <p className="mt-1 text-sm text-muted">{protocol === 'http' ? 'Connect the API first, then add only the routes the Agent needs.' : 'Tools are discovered automatically after creation.'}</p>
              </div>
            </div>

            {protocol === 'http' ? (
              <>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Base URL *</label>
                  <Input autoFocus value={baseUrl} onChange={(event) => updateBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" className="font-mono text-xs" />
                  <p className="mt-1 text-[11px] text-muted">All routes remain under this domain and base path.</p>
                  <FieldError message={errors.baseUrl} />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Display name *</label>
                  <Input value={name} onChange={(event) => { setNameTouched(true); setName(event.target.value); setErrors((current) => ({ ...current, name: '' })) }} placeholder="Public data API" />
                  <FieldError message={errors.name} />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Description *</label>
                  <Textarea value={description} onChange={(event) => { setDescription(event.target.value); setErrors((current) => ({ ...current, description: '' })) }} placeholder="Explain what this API provides so Agents understand its domain." className="min-h-[88px]" />
                  <FieldError message={errors.description} />
                </div>

                <div className="space-y-3 border-t border-border/70 pt-5">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-white">Routes</p>
                      <p className="mt-0.5 text-xs text-muted">Each route becomes an independent capability for the Agent.</p>
                    </div>
                    <Button type="button" size="sm" variant="outline" onClick={addRoute}>
                      <Plus className="mr-1.5 h-3.5 w-3.5" />
                      Add route
                    </Button>
                  </div>
                  {routes.length === 0 ? (
                    <button type="button" onClick={addRoute} className="w-full rounded-xl border border-dashed border-border/80 px-4 py-7 text-center transition-colors hover:border-primary/40 hover:bg-primary/5">
                      <Route className="mx-auto h-5 w-5 text-primary-light" />
                      <p className="mt-2 text-sm font-medium text-white">Add the first route</p>
                      <p className="mt-1 text-xs text-muted">Start with the endpoint the Agent needs most.</p>
                    </button>
                  ) : (
                    <div className="space-y-2">
                      {routes.map((route) => (
                        <div key={route.id} className="flex items-center gap-3 rounded-xl border border-border/75 bg-background/30 px-3 py-3">
                          <span className="shrink-0 rounded-md border border-border/80 bg-background px-2 py-1 font-mono text-[10px] font-semibold text-primary-light">{route.method}</span>
                          <button type="button" onClick={() => editRoute(route)} className="min-w-0 flex-1 text-left">
                            <p className="truncate text-sm font-medium text-white">{route.name}</p>
                            <p className="mt-0.5 truncate font-mono text-[11px] text-muted">{route.path}</p>
                          </button>
                          <Button type="button" size="sm" variant="ghost" className="text-red-300" onClick={() => removeRoute(route.id)} aria-label={`Remove ${route.name}`}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                  <FieldError message={errors.routes} />
                </div>

                <AdvancedSection open={detailsAdvancedOpen} onToggle={() => setDetailsAdvancedOpen((current) => !current)}>
                  <HeadersEditor headers={sharedHeaders} onChange={setSharedHeaders} />
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted">Request timeout (ms)</label>
                    <Input type="number" value={timeoutMs} min={1000} max={120000} onChange={(event) => setTimeoutMs(Number(event.target.value))} />
                  </div>
                </AdvancedSection>
              </>
            ) : (
              <>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">MCP Server URL *</label>
                  <Input autoFocus value={mcpUrl} onChange={(event) => updateMcpUrl(event.target.value)} placeholder="https://mcp.example.com/mcp" className="font-mono text-xs" />
                  <p className="mt-1 text-[11px] text-muted">Public tools are loaded automatically after creation.</p>
                  <FieldError message={errors.mcpUrl} />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Display name *</label>
                  <Input value={name} onChange={(event) => { setNameTouched(true); setName(event.target.value); setErrors((current) => ({ ...current, name: '' })) }} placeholder="Auto-filled from URL" />
                  <FieldError message={errors.name} />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Description</label>
                  <Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What this MCP provider does" className="min-h-[80px]" />
                </div>
                <AdvancedSection open={detailsAdvancedOpen} onToggle={() => setDetailsAdvancedOpen((current) => !current)}>
                  <HeadersEditor headers={mcpHeaders} onChange={setMcpHeaders} />
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted">Connection timeout (ms)</label>
                    <Input type="number" value={timeoutMs} min={1000} max={120000} onChange={(event) => setTimeoutMs(Number(event.target.value))} />
                  </div>
                </AdvancedSection>
              </>
            )}
          </div>
        ) : null}

        {step === 'route' && routeEditor ? (
          <div className="space-y-5">
            <div className="flex items-start gap-3">
              <Button type="button" size="sm" variant="ghost" className="mt-0.5 px-2" onClick={cancelCurrentStep}>
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <div>
                <h3 className="text-base font-semibold text-white">{routeEditor.isNew ? 'Add route' : 'Edit route'}</h3>
                <p className="mt-1 text-sm text-muted">Define the request first. Technical identifiers remain optional.</p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-[130px_minmax(0,1fr)]">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted">Method</label>
                <Select value={routeEditor.draft.method} onChange={(event) => updateRouteDraft({ method: event.target.value })} options={METHODS} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted">Relative path *</label>
                <Input autoFocus value={routeEditor.draft.path} onChange={(event) => { updateRouteDraft({ path: event.target.value }); setRouteErrors((current) => ({ ...current, path: '' })) }} placeholder="/employees/{{employee_id}}" className="font-mono text-xs" />
                <FieldError message={routeErrors.path} />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">Route name *</label>
              <Input value={routeEditor.draft.name} onChange={(event) => {
                const nextName = event.target.value
                updateRouteDraft({
                  name: nextName,
                  operation_id: routeEditor.draft.operation_id.startsWith('route_') ? operationId(nextName) : routeEditor.draft.operation_id,
                })
                setRouteErrors((current) => ({ ...current, name: '' }))
              }} placeholder="Search employees" />
              <FieldError message={routeErrors.name} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">Route description *</label>
              <Textarea value={routeEditor.draft.description} onChange={(event) => { updateRouteDraft({ description: event.target.value }); setRouteErrors((current) => ({ ...current, description: '' })) }} placeholder="Explain exactly when the Agent should call this route." className="min-h-[92px]" />
              <FieldError message={routeErrors.description} />
            </div>
            <div className="max-w-[220px]">
              <label className="mb-1 block text-xs font-medium text-muted">Risk</label>
              <Select value={routeEditor.draft.risk_level || 'low'} onChange={(event) => updateRouteDraft({ risk_level: event.target.value })} options={RISKS} />
            </div>

            {!['GET', 'HEAD'].includes(routeEditor.draft.method) ? (
              <div>
                <HttpRequestBodyEditor value={routeEditor.draft.body} onChange={(body) => { updateRouteDraft({ body }); setRouteErrors((current) => ({ ...current, body: '' })) }} />
                <FieldError message={routeErrors.body} />
              </div>
            ) : null}

            {routeContract?.parameterNames.length ? (
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                <span>Agent inputs</span>
                {routeContract.parameterNames.map((parameter) => <span key={parameter} className="rounded-md border border-border bg-background px-2 py-1 font-mono text-[10px] text-white">{parameter}</span>)}
              </div>
            ) : null}

            <AdvancedSection open={routeAdvancedOpen} onToggle={() => setRouteAdvancedOpen((current) => !current)}>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted">Operation ID</label>
                <Input value={routeEditor.draft.operation_id} onChange={(event) => { updateRouteDraft({ operation_id: operationId(event.target.value) }); setRouteErrors((current) => ({ ...current, operationId: '' })) }} placeholder="search_employees" className="font-mono text-xs" />
                <p className="mt-1 text-[11px] text-muted">Generated automatically from the route name.</p>
                <FieldError message={routeErrors.operationId} />
              </div>
              <HeadersEditor headers={routeEditor.draft.headers} onChange={(headers) => updateRouteDraft({ headers })} />
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Route timeout override (ms)</label>
                  <Input type="number" value={routeEditor.draft.timeout_ms || ''} min={1000} max={120000} onChange={(event) => updateRouteDraft({ timeout_ms: event.target.value ? Number(event.target.value) : undefined })} placeholder="Use group timeout" />
                </div>
                {initialTool ? (
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted">Status</label>
                    <Select value={routeEditor.draft.status || 'active'} onChange={(event) => updateRouteDraft({ status: event.target.value })} options={ROUTE_STATUSES} />
                  </div>
                ) : null}
              </div>
            </AdvancedSection>
          </div>
        ) : null}
      </div>

      <div className="sticky bottom-0 z-10 flex items-center justify-end gap-2 border-t border-border bg-surface/95 px-6 py-4 backdrop-blur">
        <Button type="button" variant="outline" onClick={cancelCurrentStep}>{step === 'route' ? 'Cancel' : cancelLabel}</Button>
        {step !== 'type' ? <Button type="submit" loading={loading} disabled={primaryDisabled}>{primaryLabel}</Button> : null}
      </div>
    </form>
  )
}
