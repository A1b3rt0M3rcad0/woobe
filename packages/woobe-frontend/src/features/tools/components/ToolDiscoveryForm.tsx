import { useCallback, useMemo, useState } from 'react'
import type { Dispatch, FormEvent, SetStateAction } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { Loader2, Play, Plus, Search, X } from 'lucide-react'
import { toast } from 'sonner'
import { useDiscoverMcpTools } from '@/features/tools/hooks'
import type {
  CreateToolRequest,
  DiscoveredMcpTool,
  HttpHeader,
  HttpToolConfig,
  McpToolConfig,
  TestToolRequest,
  TestToolResponse,
  ToolConfig,
  ToolProtocol,
} from '@/features/tools/types'

type SupportedToolProtocol = 'http' | 'mcp'

type HeaderRow = { id: string; key: string; value: string }

export type ToolFormSubmitValue = Omit<CreateToolRequest, 'project_id'>

interface ToolDiscoveryFormProps {
  submitLabel?: string
  cancelLabel?: string
  loading?: boolean
  testLoading?: boolean
  onSubmit: (value: ToolFormSubmitValue) => Promise<void>
  onCancel: () => void
  onTest?: (value: TestToolRequest) => Promise<TestToolResponse>
}

const TOOL_PROTOCOLS = [
  { value: 'http', label: 'HTTP API' },
  { value: 'mcp', label: 'MCP Server' },
]

const HTTP_METHODS = [
  { value: 'GET', label: 'GET' },
  { value: 'POST', label: 'POST' },
  { value: 'PUT', label: 'PUT' },
  { value: 'PATCH', label: 'PATCH' },
  { value: 'DELETE', label: 'DELETE' },
  { value: 'HEAD', label: 'HEAD' },
]

const RISK_LEVELS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
]

function extractUrlVariables(url: string): string[] {
  const matches = url.match(/\{\{(\w+)\}\}/g)
  if (!matches) return []
  return [...new Set(matches.map(m => m.slice(2, -2)))]
}

function displayNameForTool(tool: DiscoveredMcpTool): string {
  return tool.title || tool.name.replace(/[_-]+/g, ' ')
}

function displayNameForServer(url: string): string {
  try {
    return `MCP ${new URL(url).hostname}`
  } catch {
    return 'MCP Server'
  }
}

let nextId = 1
function headerId() {
  return `hdr_${nextId++}`
}

function toHeaderConfig(headers: HeaderRow[]): HttpHeader[] {
  return headers
    .filter(h => h.key.trim())
    .map(h => ({ key: h.key.trim(), value: h.value }))
}

function toHeaderRecord(headers: HeaderRow[]): Record<string, string> {
  return headers.reduce<Record<string, string>>((acc, h) => {
    if (h.key.trim()) acc[h.key.trim()] = h.value
    return acc
  }, {})
}

function parseJsonObject(value: string, label: string): Record<string, unknown> {
  if (!value.trim()) return {}
  const parsed = JSON.parse(value)
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object`)
  }
  return parsed as Record<string, unknown>
}

function formatTestToolResponse(result: TestToolResponse): string {
  const lines = [`Status: ${result.status_code ?? 'ok'}`]
  if (typeof result.duration_ms === 'number') lines.push(`Duration: ${Math.round(result.duration_ms)}ms`)
  if (result.output) lines.push(`Output: ${JSON.stringify(result.output, null, 2).slice(0, 2000)}`)
  if (result.body) lines.push(`Body: ${result.body.slice(0, 2000)}`)
  return lines.join('\n')
}

function HeaderEditor({
  title,
  description,
  headers,
  setHeaders,
}: {
  title: string
  description?: string
  headers: HeaderRow[]
  setHeaders: Dispatch<SetStateAction<HeaderRow[]>>
}) {
  const addHeader = () => setHeaders(prev => [...prev, { id: headerId(), key: '', value: '' }])
  const updateHeaderKey = (id: string, key: string) => setHeaders(prev => prev.map(h => h.id === id ? { ...h, key } : h))
  const updateHeaderValue = (id: string, value: string) => setHeaders(prev => prev.map(h => h.id === id ? { ...h, value } : h))
  const removeHeader = (id: string) => setHeaders(prev => prev.filter(h => h.id !== id))

  return (
    <div className="min-w-0 space-y-2 rounded-xl border border-border/70 bg-background/60 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-medium text-muted uppercase tracking-wider">{title}</p>
          {description && <p className="mt-1 text-xs text-muted break-words">{description}</p>}
        </div>
        <Button type="button" size="sm" variant="ghost" onClick={addHeader}>
          <Plus className="h-3 w-3 mr-1" />
          Add
        </Button>
      </div>
      {headers.length === 0 ? (
        <p className="text-xs text-muted italic">No headers configured</p>
      ) : (
        <div className="space-y-1.5">
          {headers.map(h => (
            <div key={h.id} className="flex min-w-0 items-center gap-1.5">
              <Input value={h.key} onChange={e => updateHeaderKey(h.id, e.target.value)} placeholder="Header" className="min-w-0 flex-1" />
              <Input value={h.value} onChange={e => updateHeaderValue(h.id, e.target.value)} placeholder="Value" className="min-w-0 flex-1" />
              <Button type="button" size="sm" variant="ghost" className="shrink-0 text-red-400 hover:text-red-300" onClick={() => removeHeader(h.id)}>
                <X className="h-3 w-3" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ToolDiscoveryForm({ submitLabel = 'Create', cancelLabel = 'Cancel', loading = false, testLoading = false, onSubmit, onCancel, onTest }: ToolDiscoveryFormProps) {
  const discoverMcpTools = useDiscoverMcpTools()
  const [protocol, setProtocol] = useState<SupportedToolProtocol>('http')
  const [displayName, setDisplayName] = useState('')
  const [description, setDescription] = useState('')
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('')
  const [httpHeaders, setHttpHeaders] = useState<HeaderRow[]>([])
  const [body, setBody] = useState('')
  const [mcpServerUrl, setMcpServerUrl] = useState('')
  const [mcpHeaders, setMcpHeaders] = useState<HeaderRow[]>([])
  const [mcpTools, setMcpTools] = useState<DiscoveredMcpTool[]>([])
  const [manualMcpToolName, setManualMcpToolName] = useState('')
  const [mcpSchema, setMcpSchema] = useState('')
  const [mcpToolTestName, setMcpToolTestName] = useState<string | null>(null)
  const [mcpToolTestInput, setMcpToolTestInput] = useState('{}')
  const [mcpToolTestLoading, setMcpToolTestLoading] = useState<string | null>(null)
  const [showMcpAdvanced, setShowMcpAdvanced] = useState(false)
  const [riskLevel, setRiskLevel] = useState('low')
  const [timeoutMs, setTimeoutMs] = useState(30000)
  const [testResult, setTestResult] = useState<string | null>(null)
  const [testError, setTestError] = useState<string | null>(null)
  const [variableValues, setVariableValues] = useState<Record<string, string>>({})

  const showBody = protocol === 'http' && ['POST', 'PUT', 'PATCH'].includes(method)
  const urlVariables = useMemo(() => extractUrlVariables(url), [url])
  const useManualMcpTool = showMcpAdvanced && manualMcpToolName.trim().length > 0

  const resetForm = useCallback(() => {
    setProtocol('http')
    setDisplayName('')
    setDescription('')
    setMethod('GET')
    setUrl('')
    setHttpHeaders([])
    setBody('')
    setMcpServerUrl('')
    setMcpHeaders([])
    setMcpTools([])
    setManualMcpToolName('')
    setMcpSchema('')
    setMcpToolTestName(null)
    setMcpToolTestInput('{}')
    setMcpToolTestLoading(null)
    setShowMcpAdvanced(false)
    setRiskLevel('low')
    setTimeoutMs(30000)
    setVariableValues({})
    setTestResult(null)
    setTestError(null)
  }, [])

  const handleUrlChange = useCallback((value: string) => {
    setUrl(value)
    const vars = extractUrlVariables(value)
    setVariableValues(prev => {
      const next = { ...prev }
      for (const v of vars) {
        if (!(v in next)) next[v] = ''
      }
      for (const k of Object.keys(next)) {
        if (!vars.includes(k)) delete next[k]
      }
      return next
    })
  }, [])

  const handleDiscoverMcpTools = async () => {
    if (!mcpServerUrl.trim()) {
      toast.error('MCP server URL is required')
      return
    }
    setMcpTools([])
    setMcpToolTestName(null)
    setTestResult(null)
    setTestError(null)
    try {
      const result = await discoverMcpTools.mutateAsync({
        server_url: mcpServerUrl.trim(),
        headers: toHeaderRecord(mcpHeaders),
        timeout_ms: timeoutMs,
      })
      if (result.tools.length === 0) {
        toast.error(result.error || 'No tools returned by this MCP server')
        return
      }
      setMcpTools(result.tools)
      if (!displayName.trim()) setDisplayName(displayNameForServer(mcpServerUrl.trim()))
      if (!description.trim()) setDescription(`${result.tools.length} MCP tools available to the agent.`)
      toast.success(`Discovered ${result.tools.length} MCP tool${result.tools.length === 1 ? '' : 's'}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'MCP discovery failed')
    }
  }

  const parseMcpSchema = () => {
    if (!mcpSchema.trim()) return undefined
    try {
      return JSON.parse(mcpSchema) as Record<string, unknown>
    } catch {
      throw new Error('MCP input schema must be valid JSON')
    }
  }

  const buildHttpConfig = (): HttpToolConfig => {
    const config: HttpToolConfig = {
      protocol: 'http',
      url: url.trim(),
      method,
      headers: toHeaderConfig(httpHeaders),
      timeout_ms: timeoutMs,
    }
    if (showBody && body.trim()) config.body = body.trim()
    if (urlVariables.length > 0) {
      config.variables = urlVariables.reduce<Record<string, string>>((acc, v) => {
        acc[v] = variableValues[v] || ''
        return acc
      }, {})
    }
    return config
  }

  const buildMcpServerConfig = () => ({
    transport: 'streamable_http' as const,
    url: mcpServerUrl.trim(),
    headers: toHeaderConfig(mcpHeaders),
  })

  const buildMcpConfig = (): McpToolConfig => {
    const manualSchema = parseMcpSchema()
    const server = buildMcpServerConfig()
    if (useManualMcpTool) {
      return {
        protocol: 'mcp',
        mode: 'tool',
        exposure: 'single',
        server,
        tool_name: manualMcpToolName.trim(),
        input_schema_source: manualSchema ? 'manual' : 'discovered',
        discovered_input_schema: manualSchema,
        timeout_ms: timeoutMs,
      }
    }
    return {
      protocol: 'mcp',
      mode: 'server',
      exposure: 'all_discovered',
      server,
      discovered_tools: mcpTools,
      discovery_cache_ttl_seconds: 3600,
      timeout_ms: timeoutMs,
    }
  }

  const buildDiscoveredMcpToolConfig = (tool: DiscoveredMcpTool): McpToolConfig => {
    const config: McpToolConfig = {
      protocol: 'mcp',
      mode: 'tool',
      exposure: 'single',
      server: buildMcpServerConfig(),
      tool_name: tool.name,
      input_schema_source: 'discovered',
      timeout_ms: timeoutMs,
    }
    if (tool.input_schema) config.discovered_input_schema = tool.input_schema
    return config
  }

  const buildConfig = (): ToolConfig => protocol === 'mcp' ? buildMcpConfig() : buildHttpConfig()

  const resolvedDisplayName = () => {
    if (displayName.trim()) return displayName.trim()
    if (protocol === 'http') return 'HTTP Tool'
    return displayNameForServer(mcpServerUrl.trim())
  }

  const validate = () => {
    if (protocol === 'http' && !url.trim()) return 'URL is required'
    if (protocol === 'mcp' && !mcpServerUrl.trim()) return 'MCP server URL is required'
    if (protocol === 'mcp' && !useManualMcpTool && mcpTools.length === 0) return 'Connect the MCP server first so ProjectRAI can discover its tools'
    if (!resolvedDisplayName()) return 'Display name is required'
    return null
  }

  const buildSubmitValue = (): ToolFormSubmitValue => ({
    name: resolvedDisplayName(),
    description: description.trim() || (protocol === 'mcp' ? `${mcpTools.length} MCP tools available to the agent.` : undefined),
    type: protocol as ToolProtocol,
    config: buildConfig(),
    input_schema: useManualMcpTool ? parseMcpSchema() : undefined,
    risk_level: riskLevel,
    timeout_ms: timeoutMs,
  })

  const handleTest = async () => {
    if (!onTest) return
    const error = validate()
    if (error) {
      toast.error(error)
      return
    }
    setTestResult(null)
    setTestError(null)
    try {
      const result = await onTest({
        type: protocol as ToolProtocol,
        config: buildConfig(),
        timeout_ms: timeoutMs,
      })
      if (result.success) {
        setTestResult(formatTestToolResponse(result))
        toast.success('Tool test succeeded')
      } else {
        setTestError(result.error || result.body || 'Request failed')
        toast.error('Tool test failed')
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Test request failed'
      setTestError(msg)
      toast.error(msg)
    }
  }

  const handleDiscoveredMcpToolTest = async (tool: DiscoveredMcpTool) => {
    if (!onTest) return
    if (!mcpServerUrl.trim()) {
      toast.error('MCP server URL is required')
      return
    }

    let inputData: Record<string, unknown>
    try {
      inputData = parseJsonObject(mcpToolTestInput, 'MCP tool input')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'MCP tool input must be valid JSON'
      setTestError(msg)
      toast.error(msg)
      return
    }

    setTestResult(null)
    setTestError(null)
    setMcpToolTestLoading(tool.name)
    try {
      const result = await onTest({
        type: 'mcp',
        config: buildDiscoveredMcpToolConfig(tool),
        input_data: inputData,
        timeout_ms: timeoutMs,
      })
      if (result.success) {
        setTestResult(formatTestToolResponse(result))
        toast.success('MCP tool test succeeded')
      } else {
        setTestError(result.error || result.body || 'MCP tool test failed')
        toast.error('MCP tool test failed')
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'MCP tool test failed'
      setTestError(msg)
      toast.error(msg)
    } finally {
      setMcpToolTestLoading(null)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const error = validate()
    if (error) {
      toast.error(error)
      return
    }
    try {
      await onSubmit(buildSubmitValue())
      resetForm()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save tool')
    }
  }

  const handleCancel = () => {
    resetForm()
    onCancel()
  }

  return (
    <form onSubmit={handleSubmit} className="min-w-0 space-y-5 overflow-x-hidden">
      <div className="min-w-0 rounded-2xl border border-border/80 bg-background/80 p-4 shadow-sm">
        <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary-light">Tool runtime</p>
            <p className="mt-1 text-sm text-muted break-words">Choose how ProjectRAI should execute this capability.</p>
          </div>
          <div className="w-full sm:w-44">
            <Select value={protocol} onChange={e => setProtocol(e.target.value as SupportedToolProtocol)} options={TOOL_PROTOCOLS} />
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <button type="button" onClick={() => setProtocol('http')} className={`min-w-0 rounded-xl border p-3 text-left transition ${protocol === 'http' ? 'border-primary/60 bg-primary/10 text-white' : 'border-border bg-card/60 text-muted hover:border-border-light'}`}>
            <p className="text-sm font-medium break-words">HTTP API</p>
            <p className="mt-1 text-xs text-muted break-words">Call a REST-style endpoint directly.</p>
          </button>
          <button type="button" onClick={() => setProtocol('mcp')} className={`min-w-0 rounded-xl border p-3 text-left transition ${protocol === 'mcp' ? 'border-primary/60 bg-primary/10 text-white' : 'border-border bg-card/60 text-muted hover:border-border-light'}`}>
            <p className="text-sm font-medium break-words">MCP Server</p>
            <p className="mt-1 text-xs text-muted break-words">Connect a server and let the agent choose any discovered tool.</p>
          </button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="min-w-0">
          <label className="block text-xs font-medium text-muted mb-1">Display name</label>
          <Input value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder={protocol === 'mcp' ? 'Auto-filled after connection' : 'Fetch Customer'} />
        </div>
        <div className="min-w-0">
          <label className="block text-xs font-medium text-muted mb-1">Risk Level</label>
          <Select value={riskLevel} onChange={e => setRiskLevel(e.target.value)} options={RISK_LEVELS} />
        </div>
      </div>

      <div className="min-w-0">
        <label className="block text-xs font-medium text-muted mb-1">Description</label>
        <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="What this tool provider does and when the agent should use it" />
      </div>

      {protocol === 'http' ? (
        <div className="min-w-0 space-y-4 overflow-hidden rounded-2xl border border-border/80 bg-card/40 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="text-sm font-medium text-white">HTTP request</p>
              <p className="mt-1 text-xs text-muted break-words">Use template variables like {'{{customerId}}'} in the URL.</p>
            </div>
            <div className="w-full sm:w-32"><Select value={method} onChange={e => setMethod(e.target.value)} options={HTTP_METHODS} /></div>
          </div>
          <div className="min-w-0">
            <label className="block text-xs font-medium text-muted mb-1">URL *</label>
            <Input value={url} onChange={e => handleUrlChange(e.target.value)} placeholder="https://api.example.com/customers/{{customerId}}" />
          </div>
          {urlVariables.length > 0 && (
            <div className="min-w-0 rounded-xl border border-border/70 bg-background/60 p-3 space-y-2">
              <p className="text-[10px] font-medium text-muted uppercase tracking-wider">URL Variables</p>
              {urlVariables.map(v => (
                <div key={v} className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center">
                  <span className="text-xs font-mono text-muted break-all sm:min-w-[120px]">{'{{'}{v}{'}}'}</span>
                  <Input value={variableValues[v] || ''} onChange={e => setVariableValues(prev => ({ ...prev, [v]: e.target.value }))} placeholder={`Default value for ${v}`} className="min-w-0 flex-1" />
                </div>
              ))}
            </div>
          )}
          {showBody && <div className="min-w-0"><label className="block text-xs font-medium text-muted mb-1">Body</label><Textarea value={body} onChange={e => setBody(e.target.value)} placeholder='{"key": "value"}' className="min-h-[100px] font-mono text-xs" /></div>}
          <HeaderEditor title="HTTP Headers" description="Optional request headers." headers={httpHeaders} setHeaders={setHttpHeaders} />
        </div>
      ) : (
        <div className="min-w-0 space-y-4 overflow-hidden rounded-2xl border border-border/80 bg-card/40 p-4">
          <div className="min-w-0 rounded-xl border border-blue-500/30 bg-blue-500/5 p-3">
            <p className="text-sm font-medium text-blue-200 break-words">Connect MCP server</p>
            <p className="mt-1 text-xs text-muted break-words">Connect once. ProjectRAI will expose all discovered server tools to the agent and the model will decide which one to call.</p>
          </div>
          <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-end">
            <div className="min-w-0 flex-1">
              <label className="block text-xs font-medium text-muted mb-1">MCP Server URL *</label>
              <Input value={mcpServerUrl} onChange={e => setMcpServerUrl(e.target.value)} placeholder="https://mcp.example.com" />
            </div>
            <Button type="button" variant="outline" onClick={handleDiscoverMcpTools} disabled={discoverMcpTools.isPending} className="w-full sm:w-auto sm:shrink-0">
              {discoverMcpTools.isPending ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Search className="h-3 w-3 mr-1" />}
              Connect
            </Button>
          </div>

          {mcpTools.length > 0 && (
            <div className="min-w-0 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[10px] font-medium text-muted uppercase tracking-wider">Available to agent</p>
                {mcpTools.length > 2 && <p className="text-[10px] text-muted">Scroll to view all</p>}
              </div>
              <p className="text-xs text-muted">{mcpTools.length} tools discovered. The agent can choose any of them automatically.</p>
              <div className={`grid min-w-0 gap-2 pr-1 ${mcpTools.length > 2 ? 'max-h-64 overflow-y-auto overscroll-contain' : ''}`}>
                {mcpTools.map(tool => (
                  <div key={tool.name} className="w-full min-w-0 overflow-hidden rounded-xl border border-border bg-background/60 p-3 text-left">
                    <div className="flex min-w-0 items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium break-words text-white">{displayNameForTool(tool)}</p>
                        <p className="mt-1 text-[11px] font-mono text-muted break-all">{tool.name}</p>
                      </div>
                      {onTest && (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="shrink-0"
                          onClick={() => {
                            setMcpToolTestName(prev => prev === tool.name ? null : tool.name)
                            setMcpToolTestInput('{}')
                            setTestResult(null)
                            setTestError(null)
                          }}
                        >
                          <Play className="h-3 w-3 mr-1" />
                          Test
                        </Button>
                      )}
                    </div>
                    {tool.description && <p className="mt-1 text-xs text-muted break-words">{tool.description}</p>}
                    {mcpToolTestName === tool.name && (
                      <div className="mt-3 min-w-0 space-y-2 rounded-lg border border-border/70 bg-card/50 p-3">
                        <label className="block text-xs font-medium text-muted">Input JSON</label>
                        <Textarea
                          value={mcpToolTestInput}
                          onChange={e => setMcpToolTestInput(e.target.value)}
                          placeholder='{"query":"example"}'
                          className="min-h-[90px] font-mono text-xs"
                        />
                        <div className="flex justify-end">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => handleDiscoveredMcpToolTest(tool)}
                            disabled={testLoading || Boolean(mcpToolTestLoading)}
                          >
                            {mcpToolTestLoading === tool.name ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Play className="h-3 w-3 mr-1" />}
                            Run test
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <button type="button" onClick={() => setShowMcpAdvanced(prev => !prev)} className="text-xs font-medium text-primary-light hover:text-primary">
            {showMcpAdvanced ? 'Hide advanced MCP settings' : 'Show advanced MCP settings'}
          </button>

          {showMcpAdvanced && (
            <div className="min-w-0 space-y-3 overflow-hidden rounded-xl border border-border/70 bg-background/50 p-3">
              <HeaderEditor title="MCP Server Headers" description="Optional headers for discovery and calls." headers={mcpHeaders} setHeaders={setMcpHeaders} />
              <div className="min-w-0">
                <label className="block text-xs font-medium text-muted mb-1">Single tool override</label>
                <Input value={manualMcpToolName} onChange={e => setManualMcpToolName(e.target.value)} placeholder="Optional: expose only this tool name" />
              </div>
              <div className="min-w-0">
                <label className="block text-xs font-medium text-muted mb-1">Manual Input Schema JSON</label>
                <Textarea value={mcpSchema} onChange={e => setMcpSchema(e.target.value)} placeholder='{"type":"object","properties":{}}' className="min-h-[100px] font-mono text-xs" />
              </div>
            </div>
          )}
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <div className="min-w-0"><label className="block text-xs font-medium text-muted mb-1">Timeout (ms)</label><Input type="number" value={timeoutMs} onChange={e => setTimeoutMs(Number(e.target.value))} min={1000} max={120000} /></div>
      </div>

      {testResult && <div className="min-w-0 rounded-lg border border-green-500/30 bg-green-500/5 p-3"><pre className="text-xs text-green-300 whitespace-pre-wrap break-words font-mono">{testResult}</pre></div>}
      {testError && <div className="min-w-0 rounded-lg border border-red-500/30 bg-red-500/5 p-3"><pre className="text-xs text-red-300 whitespace-pre-wrap break-words font-mono">{testError}</pre></div>}

      <div className="flex flex-col justify-between gap-2 pt-2 border-t border-border sm:flex-row">
        {onTest ? <Button type="button" size="sm" variant="outline" onClick={handleTest} disabled={testLoading || (protocol === 'mcp' && !useManualMcpTool)}>{testLoading ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Play className="h-3 w-3 mr-1" />}Test</Button> : <span />}
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-end"><Button type="button" variant="outline" onClick={handleCancel}>{cancelLabel}</Button><Button type="submit" loading={loading}>{submitLabel}</Button></div>
      </div>
    </form>
  )
}
