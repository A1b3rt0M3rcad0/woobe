import { useCallback, useMemo, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { Loader2, Play, Plus, X } from 'lucide-react'
import { toast } from 'sonner'
import type {
  CreateToolRequest,
  HttpHeader,
  HttpToolConfig,
  McpToolConfig,
  TestToolRequest,
  TestToolResponse,
  ToolConfig,
  ToolProtocol,
} from '@/features/tools/types'

type SupportedToolProtocol = 'http' | 'mcp'

export type ToolFormSubmitValue = Omit<CreateToolRequest, 'project_id'>

interface ToolFormProps {
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
  { value: 'mcp', label: 'MCP Tool' },
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

let nextId = 1
function headerId() {
  return `hdr_${nextId++}`
}

function toHeaderConfig(headers: { id: string; key: string; value: string }[]): HttpHeader[] {
  return headers
    .filter(h => h.key.trim())
    .map(h => ({ key: h.key.trim(), value: h.value }))
}

function HeaderEditor({
  title,
  description,
  headers,
  setHeaders,
}: {
  title: string
  description?: string
  headers: { id: string; key: string; value: string }[]
  setHeaders: React.Dispatch<React.SetStateAction<{ id: string; key: string; value: string }[]>>
}) {
  const addHeader = () => setHeaders(prev => [...prev, { id: headerId(), key: '', value: '' }])
  const updateHeaderKey = (id: string, key: string) => setHeaders(prev => prev.map(h => h.id === id ? { ...h, key } : h))
  const updateHeaderValue = (id: string, value: string) => setHeaders(prev => prev.map(h => h.id === id ? { ...h, value } : h))
  const removeHeader = (id: string) => setHeaders(prev => prev.filter(h => h.id !== id))

  return (
    <div className="space-y-2 rounded-xl border border-border/70 bg-background/60 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-medium text-muted uppercase tracking-wider">{title}</p>
          {description && <p className="mt-1 text-xs text-muted">{description}</p>}
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
            <div key={h.id} className="flex items-center gap-1.5">
              <Input value={h.key} onChange={e => updateHeaderKey(h.id, e.target.value)} placeholder="Header" className="flex-1" />
              <Input value={h.value} onChange={e => updateHeaderValue(h.id, e.target.value)} placeholder="Value" className="flex-1" />
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

export function ToolForm({ submitLabel = 'Create', cancelLabel = 'Cancel', loading = false, testLoading = false, onSubmit, onCancel, onTest }: ToolFormProps) {
  const [protocol, setProtocol] = useState<SupportedToolProtocol>('http')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('')
  const [httpHeaders, setHttpHeaders] = useState<{ id: string; key: string; value: string }[]>([])
  const [body, setBody] = useState('')
  const [mcpServerUrl, setMcpServerUrl] = useState('')
  const [mcpToolName, setMcpToolName] = useState('')
  const [mcpHeaders, setMcpHeaders] = useState<{ id: string; key: string; value: string }[]>([])
  const [mcpSchema, setMcpSchema] = useState('')
  const [showMcpAdvanced, setShowMcpAdvanced] = useState(false)
  const [riskLevel, setRiskLevel] = useState('low')
  const [timeoutMs, setTimeoutMs] = useState(30000)
  const [testResult, setTestResult] = useState<string | null>(null)
  const [testError, setTestError] = useState<string | null>(null)

  const showBody = protocol === 'http' && ['POST', 'PUT', 'PATCH'].includes(method)
  const urlVariables = useMemo(() => extractUrlVariables(url), [url])
  const [variableValues, setVariableValues] = useState<Record<string, string>>({})

  const resetForm = useCallback(() => {
    setProtocol('http')
    setName('')
    setDescription('')
    setMethod('GET')
    setUrl('')
    setHttpHeaders([])
    setBody('')
    setMcpServerUrl('')
    setMcpToolName('')
    setMcpHeaders([])
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
    return {
      protocol: 'mcp',
      server: {
        transport: 'streamable_http',
        url: mcpServerUrl.trim(),
        headers: toHeaderConfig(mcpHeaders),
      },
      tool_name: mcpToolName.trim(),
      input_schema_source: manualSchema ? 'manual' : 'discovered',
      discovered_input_schema: manualSchema,
      timeout_ms: timeoutMs,
    }
  }

  const buildConfig = (): ToolConfig => protocol === 'mcp' ? buildMcpConfig() : buildHttpConfig()

  const validate = () => {
    if (!name.trim()) return 'Tool name is required'
    if (protocol === 'http' && !url.trim()) return 'URL is required'
    if (protocol === 'mcp' && !mcpServerUrl.trim()) return 'MCP server URL is required'
    if (protocol === 'mcp' && !mcpToolName.trim()) return 'MCP tool name is required'
    return null
  }

  const buildSubmitValue = (): ToolFormSubmitValue => ({
    name: name.trim(),
    description: description.trim() || undefined,
    type: protocol as ToolProtocol,
    config: buildConfig(),
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
      const request: TestToolRequest = {
        type: protocol as ToolProtocol,
        config: buildConfig(),
        timeout_ms: timeoutMs,
      }
      const result = await onTest(request)
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

  const handleSubmit = async (e: React.FormEvent) => {
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
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="rounded-2xl border border-border/80 bg-background/80 p-4 shadow-sm">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary-light">Tool runtime</p>
            <p className="mt-1 text-sm text-muted">Choose how ProjectRAI should execute this capability.</p>
          </div>
          <div className="w-44">
            <Select value={protocol} onChange={e => setProtocol(e.target.value as SupportedToolProtocol)} options={TOOL_PROTOCOLS} />
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <button
            type="button"
            onClick={() => setProtocol('http')}
            className={`rounded-xl border p-3 text-left transition ${protocol === 'http' ? 'border-primary/60 bg-primary/10 text-white' : 'border-border bg-card/60 text-muted hover:border-border-light'}`}
          >
            <p className="text-sm font-medium">HTTP API</p>
            <p className="mt-1 text-xs text-muted">Call a REST-style endpoint directly with URL, method, headers and optional body.</p>
          </button>
          <button
            type="button"
            onClick={() => setProtocol('mcp')}
            className={`rounded-xl border p-3 text-left transition ${protocol === 'mcp' ? 'border-primary/60 bg-primary/10 text-white' : 'border-border bg-card/60 text-muted hover:border-border-light'}`}
          >
            <p className="text-sm font-medium">MCP Tool</p>
            <p className="mt-1 text-xs text-muted">Call one tool exposed by a remote MCP server over Streamable HTTP.</p>
          </button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Name *</label>
          <Input value={name} onChange={e => setName(e.target.value)} placeholder={protocol === 'mcp' ? 'Search Knowledge Base' : 'Fetch Customer'} />
        </div>
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Risk Level</label>
          <Select value={riskLevel} onChange={e => setRiskLevel(e.target.value)} options={RISK_LEVELS} />
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-muted mb-1">Description</label>
        <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="What this tool does and when the agent should use it" />
      </div>

      {protocol === 'http' ? (
        <div className="space-y-4 rounded-2xl border border-border/80 bg-card/40 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-white">HTTP request</p>
              <p className="mt-1 text-xs text-muted">Use template variables like {'{{customerId}}'} in the URL.</p>
            </div>
            <div className="w-32">
              <Select value={method} onChange={e => setMethod(e.target.value)} options={HTTP_METHODS} />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-muted mb-1">URL *</label>
            <Input value={url} onChange={e => handleUrlChange(e.target.value)} placeholder="https://api.example.com/customers/{{customerId}}" />
          </div>

          {urlVariables.length > 0 && (
            <div className="rounded-xl border border-border/70 bg-background/60 p-3 space-y-2">
              <p className="text-[10px] font-medium text-muted uppercase tracking-wider">URL Variables</p>
              {urlVariables.map(v => (
                <div key={v} className="flex items-center gap-2">
                  <span className="text-xs font-mono text-muted min-w-[120px]">{'{{'}{v}{'}}'}</span>
                  <Input value={variableValues[v] || ''} onChange={e => setVariableValues(prev => ({ ...prev, [v]: e.target.value }))} placeholder={`Default value for ${v}`} className="flex-1" />
                </div>
              ))}
            </div>
          )}

          {showBody && (
            <div>
              <label className="block text-xs font-medium text-muted mb-1">Body</label>
              <Textarea value={body} onChange={e => setBody(e.target.value)} placeholder='{"key": "value"}' className="min-h-[100px] font-mono text-xs" />
            </div>
          )}

          <HeaderEditor
            title="HTTP Headers"
            description="Optional request headers. Secret references can be added later through credentials."
            headers={httpHeaders}
            setHeaders={setHttpHeaders}
          />
        </div>
      ) : (
        <div className="space-y-4 rounded-2xl border border-border/80 bg-card/40 p-4">
          <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-3">
            <p className="text-sm font-medium text-blue-200">Remote MCP over Streamable HTTP</p>
            <p className="mt-1 text-xs text-muted">
              For this MVP, ProjectRAI connects to a remote MCP server and calls one exposed tool. Local STDIO and legacy SSE are intentionally hidden from the basic form.
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <label className="block text-xs font-medium text-muted mb-1">MCP Server URL *</label>
              <Input value={mcpServerUrl} onChange={e => setMcpServerUrl(e.target.value)} placeholder="https://mcp.example.com" />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted mb-1">MCP Tool Name *</label>
              <Input value={mcpToolName} onChange={e => setMcpToolName(e.target.value)} placeholder="search_documents" />
            </div>
          </div>

          <button
            type="button"
            onClick={() => setShowMcpAdvanced(prev => !prev)}
            className="text-xs font-medium text-primary-light hover:text-primary"
          >
            {showMcpAdvanced ? 'Hide advanced MCP settings' : 'Show advanced MCP settings'}
          </button>

          {showMcpAdvanced && (
            <div className="space-y-3 rounded-xl border border-border/70 bg-background/50 p-3">
              <HeaderEditor
                title="MCP Server Headers"
                description="Optional headers for the remote MCP server, for example authorization or tenant routing."
                headers={mcpHeaders}
                setHeaders={setMcpHeaders}
              />
              <div>
                <label className="block text-xs font-medium text-muted mb-1">Manual Input Schema JSON</label>
                <Textarea
                  value={mcpSchema}
                  onChange={e => setMcpSchema(e.target.value)}
                  placeholder='{"type":"object","properties":{}}'
                  className="min-h-[100px] font-mono text-xs"
                />
                <p className="mt-1 text-[10px] text-muted">Leave blank to let the runtime use discovered schema metadata when available.</p>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Timeout (ms)</label>
          <Input type="number" value={timeoutMs} onChange={e => setTimeoutMs(Number(e.target.value))} min={1000} max={120000} />
        </div>
      </div>

      {testResult && <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-3"><pre className="text-xs text-green-300 whitespace-pre-wrap font-mono">{testResult}</pre></div>}
      {testError && <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3"><pre className="text-xs text-red-300 whitespace-pre-wrap font-mono">{testError}</pre></div>}

      <div className="flex justify-between gap-2 pt-2 border-t border-border">
        {onTest ? (
          <Button type="button" size="sm" variant="outline" onClick={handleTest} disabled={testLoading}>
            {testLoading ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Play className="h-3 w-3 mr-1" />}
            Test
          </Button>
        ) : <span />}
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={handleCancel}>{cancelLabel}</Button>
          <Button type="submit" loading={loading}>{submitLabel}</Button>
        </div>
      </div>
    </form>
  )
}
