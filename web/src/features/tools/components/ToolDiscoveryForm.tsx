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
  const [selectedMcpTool, setSelectedMcpTool] = useState('')
  const [manualMcpToolName, setManualMcpToolName] = useState('')
  const [mcpSchema, setMcpSchema] = useState('')
  const [showMcpAdvanced, setShowMcpAdvanced] = useState(false)
  const [riskLevel, setRiskLevel] = useState('low')
  const [timeoutMs, setTimeoutMs] = useState(30000)
  const [testResult, setTestResult] = useState<string | null>(null)
  const [testError, setTestError] = useState<string | null>(null)
  const [variableValues, setVariableValues] = useState<Record<string, string>>({})

  const showBody = protocol === 'http' && ['POST', 'PUT', 'PATCH'].includes(method)
  const urlVariables = useMemo(() => extractUrlVariables(url), [url])
  const selectedTool = useMemo(
    () => mcpTools.find(tool => tool.name === selectedMcpTool),
    [mcpTools, selectedMcpTool],
  )

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
    setSelectedMcpTool('')
    setManualMcpToolName('')
    setMcpSchema('')
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
    setSelectedMcpTool('')
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
      const first = result.tools[0]
      setSelectedMcpTool(first.name)
      if (!displayName.trim()) setDisplayName(displayNameForTool(first))
      if (!description.trim() && first.description) setDescription(first.description)
      toast.success(`Discovered ${result.tools.length} MCP tool${result.tools.length === 1 ? '' : 's'}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'MCP discovery failed')
    }
  }

  const selectMcpTool = (tool: DiscoveredMcpTool) => {
    setSelectedMcpTool(tool.name)
    if (!displayName.trim()) setDisplayName(displayNameForTool(tool))
    if (!description.trim() && tool.description) setDescription(tool.description)
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

  const buildMcpConfig = (): McpToolConfig => {
    const manualSchema = parseMcpSchema()
    const toolName = selectedTool?.name || manualMcpToolName.trim()
    return {
      protocol: 'mcp',
      server: {
        transport: 'streamable_http',
        url: mcpServerUrl.trim(),
        headers: toHeaderConfig(mcpHeaders),
      },
      tool_name: toolName,
      input_schema_source: manualSchema ? 'manual' : 'discovered',
      discovered_input_schema: manualSchema || selectedTool?.input_schema || undefined,
      timeout_ms: timeoutMs,
    }
  }

  const buildConfig = (): ToolConfig => protocol === 'mcp' ? buildMcpConfig() : buildHttpConfig()

  const resolvedDisplayName = () => {
    if (displayName.trim()) return displayName.trim()
    if (selectedTool) return displayNameForTool(selectedTool)
    if (protocol === 'http') return 'HTTP Tool'
    return manualMcpToolName.trim()
  }

  const validate = () => {
    if (protocol === 'http' && !url.trim()) return 'URL is required'
    if (protocol === 'mcp' && !mcpServerUrl.trim()) return 'MCP server URL is required'
    if (protocol === 'mcp' && !selectedTool && !manualMcpToolName.trim()) return 'Discover and select a tool from the MCP server first'
    if (!resolvedDisplayName()) return 'Display name is required'
    return null
  }

  const buildSubmitValue = (): ToolFormSubmitValue => ({
    name: resolvedDisplayName(),
    description: description.trim() || selectedTool?.description || undefined,
    type: protocol as ToolProtocol,
    config: buildConfig(),
    input_schema: protocol === 'mcp' ? selectedTool?.input_schema || parseMcpSchema() : undefined,
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
        setTestResult(`Status: ${result.status_code ?? 'ok'}\nBody: ${result.body?.slice(0, 500) ?? ''}`)
        toast.success('Tool test succeeded')
      } else {
        setTestError(result.error || 'Request failed')
        toast.error('Tool test failed')
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Test request failed'
      setTestError(msg)
      toast.error(msg)
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
            <p className="mt-1 text-xs text-muted break-words">Connect a server, discover tools, then select one.</p>
          </button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="min-w-0">
          <label className="block text-xs font-medium text-muted mb-1">Display name</label>
          <Input value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder={protocol === 'mcp' ? 'Auto-filled after discovery' : 'Fetch Customer'} />
        </div>
        <div className="min-w-0">
          <label className="block text-xs font-medium text-muted mb-1">Risk Level</label>
          <Select value={riskLevel} onChange={e => setRiskLevel(e.target.value)} options={RISK_LEVELS} />
        </div>
      </div>

      <div className="min-w-0">
        <label className="block text-xs font-medium text-muted mb-1">Description</label>
        <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="What this tool does and when the agent should use it" />
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
            <p className="mt-1 text-xs text-muted break-words">Enter the server URL and let ProjectRAI discover the available tools. You do not need to type the technical MCP tool name manually.</p>
          </div>
          <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-end">
            <div className="min-w-0 flex-1">
              <label className="block text-xs font-medium text-muted mb-1">MCP Server URL *</label>
              <Input value={mcpServerUrl} onChange={e => setMcpServerUrl(e.target.value)} placeholder="https://mcp.example.com" />
            </div>
            <Button type="button" variant="outline" onClick={handleDiscoverMcpTools} disabled={discoverMcpTools.isPending} className="w-full sm:w-auto sm:shrink-0">
              {discoverMcpTools.isPending ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Search className="h-3 w-3 mr-1" />}
              Discover
            </Button>
          </div>

          {mcpTools.length > 0 && (
            <div className="min-w-0 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[10px] font-medium text-muted uppercase tracking-wider">Discovered tools</p>
                {mcpTools.length > 2 && <p className="text-[10px] text-muted">Scroll to view all</p>}
              </div>
              <div className={`grid min-w-0 gap-2 pr-1 ${mcpTools.length > 2 ? 'max-h-64 overflow-y-auto overscroll-contain' : ''}`}>
                {mcpTools.map(tool => (
                  <button key={tool.name} type="button" onClick={() => selectMcpTool(tool)} className={`w-full min-w-0 overflow-hidden rounded-xl border p-3 text-left transition ${selectedMcpTool === tool.name ? 'border-primary/60 bg-primary/10 text-white' : 'border-border bg-background/60 text-muted hover:border-border-light'}`}>
                    <p className="text-sm font-medium break-words">{displayNameForTool(tool)}</p>
                    <p className="mt-1 text-[11px] font-mono text-muted break-all">{tool.name}</p>
                    {tool.description && <p className="mt-1 text-xs text-muted break-words">{tool.description}</p>}
                  </button>
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
                <label className="block text-xs font-medium text-muted mb-1">Manual tool name fallback</label>
                <Input value={manualMcpToolName} onChange={e => setManualMcpToolName(e.target.value)} placeholder="Only use if discovery is unavailable" />
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
        {onTest ? <Button type="button" size="sm" variant="outline" onClick={handleTest} disabled={testLoading}>{testLoading ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Play className="h-3 w-3 mr-1" />}Test</Button> : <span />}
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-end"><Button type="button" variant="outline" onClick={handleCancel}>{cancelLabel}</Button><Button type="submit" loading={loading}>{submitLabel}</Button></div>
      </div>
    </form>
  )
}
