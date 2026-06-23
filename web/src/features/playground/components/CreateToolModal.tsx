import { useState, useMemo, useCallback } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Select } from '@/components/ui/Select'
import { Plus, X, Play, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useCreateTool, useTestTool } from '@/features/tools/hooks'
import type { Tool, ToolConfig, ToolProtocol } from '@/features/tools/types'

interface CreateToolModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  onCreated: (tool: Tool) => void
}

const TOOL_PROTOCOLS = [
  { value: 'http', label: 'HTTP' },
  { value: 'mcp', label: 'MCP' },
]

const HTTP_METHODS = [
  { value: 'GET', label: 'GET' },
  { value: 'POST', label: 'POST' },
  { value: 'PUT', label: 'PUT' },
  { value: 'PATCH', label: 'PATCH' },
  { value: 'DELETE', label: 'DELETE' },
  { value: 'HEAD', label: 'HEAD' },
]

const MCP_TRANSPORTS = [
  { value: 'streamable_http', label: 'Streamable HTTP' },
  { value: 'sse', label: 'SSE' },
  { value: 'stdio', label: 'STDIO' },
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

export function CreateToolModal({ open, onClose, projectId, onCreated }: CreateToolModalProps) {
  const [protocol, setProtocol] = useState<ToolProtocol>('http')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('')
  const [headers, setHeaders] = useState<{ id: string; key: string; value: string }[]>([])
  const [body, setBody] = useState('')
  const [mcpTransport, setMcpTransport] = useState<'streamable_http' | 'sse' | 'stdio'>('streamable_http')
  const [mcpServerUrl, setMcpServerUrl] = useState('')
  const [mcpCommand, setMcpCommand] = useState('')
  const [mcpToolName, setMcpToolName] = useState('')
  const [mcpSchema, setMcpSchema] = useState('')
  const [riskLevel, setRiskLevel] = useState('low')
  const [timeoutMs, setTimeoutMs] = useState(30000)

  const createTool = useCreateTool()
  const testTool = useTestTool()

  const [testResult, setTestResult] = useState<string | null>(null)
  const [testError, setTestError] = useState<string | null>(null)

  const showBody = protocol === 'http' && ['POST', 'PUT', 'PATCH'].includes(method)
  const urlVariables = useMemo(() => extractUrlVariables(url), [url])
  const [variableValues, setVariableValues] = useState<Record<string, string>>({})

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

  const addHeader = () => {
    setHeaders(prev => [...prev, { id: headerId(), key: '', value: '' }])
  }

  const updateHeaderKey = (id: string, key: string) => {
    setHeaders(prev => prev.map(h => h.id === id ? { ...h, key } : h))
  }

  const updateHeaderValue = (id: string, value: string) => {
    setHeaders(prev => prev.map(h => h.id === id ? { ...h, value } : h))
  }

  const removeHeader = (id: string) => {
    setHeaders(prev => prev.filter(h => h.id !== id))
  }

  const resetForm = () => {
    setProtocol('http')
    setName('')
    setDescription('')
    setMethod('GET')
    setUrl('')
    setHeaders([])
    setBody('')
    setMcpTransport('streamable_http')
    setMcpServerUrl('')
    setMcpCommand('')
    setMcpToolName('')
    setMcpSchema('')
    setRiskLevel('low')
    setTimeoutMs(30000)
    setVariableValues({})
    setTestResult(null)
    setTestError(null)
  }

  const buildHttpConfig = (): ToolConfig => {
    const config: Record<string, unknown> = {
      protocol: 'http',
      url: url.trim(),
      method,
      headers: headers.filter(h => h.key.trim()).map(h => ({ key: h.key.trim(), value: h.value })),
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

  const buildMcpConfig = (): ToolConfig => {
    const config: Record<string, unknown> = {
      protocol: 'mcp',
      server: {
        transport: mcpTransport,
        url: mcpServerUrl.trim() || undefined,
        command: mcpCommand.trim() || undefined,
        headers: headers.filter(h => h.key.trim()).map(h => ({ key: h.key.trim(), value: h.value })),
      },
      tool_name: mcpToolName.trim(),
      input_schema_source: mcpSchema.trim() ? 'manual' : 'discovered',
      timeout_ms: timeoutMs,
    }
    if (mcpSchema.trim()) {
      try {
        config.discovered_input_schema = JSON.parse(mcpSchema)
      } catch {
        throw new Error('MCP input schema must be valid JSON')
      }
    }
    return config
  }

  const buildConfig = (): ToolConfig => protocol === 'mcp' ? buildMcpConfig() : buildHttpConfig()

  const validate = () => {
    if (!name.trim()) return 'Tool name is required'
    if (protocol === 'http' && !url.trim()) return 'URL is required'
    if (protocol === 'mcp' && mcpTransport !== 'stdio' && !mcpServerUrl.trim()) return 'MCP server URL is required'
    if (protocol === 'mcp' && mcpTransport === 'stdio' && !mcpCommand.trim()) return 'MCP stdio command is required'
    if (protocol === 'mcp' && !mcpToolName.trim()) return 'MCP tool name is required'
    return null
  }

  const handleTest = async () => {
    const error = validate()
    if (error) {
      toast.error(error)
      return
    }
    setTestResult(null)
    setTestError(null)
    try {
      const result = await testTool.mutateAsync({
        type: protocol,
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const error = validate()
    if (error) {
      toast.error(error)
      return
    }

    try {
      const tool = await createTool.mutateAsync({
        project_id: projectId,
        name: name.trim(),
        description: description.trim() || undefined,
        type: protocol,
        config: buildConfig(),
        risk_level: riskLevel,
        timeout_ms: timeoutMs,
      })
      onCreated(tool)
      resetForm()
      onClose()
      toast.success(`Tool "${tool.name}" created. Use Import to add it to this agent.`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create tool')
    }
  }

  const handleClose = () => {
    resetForm()
    onClose()
  }

  return (
    <Dialog open={open} onClose={handleClose} title="Create Tool">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Protocol</label>
            <Select value={protocol} onChange={e => setProtocol(e.target.value as ToolProtocol)} options={TOOL_PROTOCOLS} />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Timeout (ms)</label>
            <Input type="number" value={timeoutMs} onChange={e => setTimeoutMs(Number(e.target.value))} min={1000} max={120000} />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Name *</label>
          <Input value={name} onChange={e => setName(e.target.value)} placeholder={protocol === 'mcp' ? 'My MCP Tool' : 'My HTTP Tool'} />
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Description</label>
          <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="Optional description" />
        </div>

        {protocol === 'http' ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-muted mb-1">HTTP Method</label>
                <Select value={method} onChange={e => setMethod(e.target.value)} options={HTTP_METHODS} />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-muted mb-1">URL *</label>
              <Input value={url} onChange={e => handleUrlChange(e.target.value)} placeholder="https://api.example.com/users/{{userId}}" />
              <p className="text-[10px] text-muted mt-1">Use {'{{variableName}}'} for dynamic values in the URL</p>
            </div>

            {urlVariables.length > 0 && (
              <div className="rounded-lg border border-border bg-background p-3 space-y-2">
                <p className="text-[10px] font-medium text-muted uppercase tracking-wider">URL Variables</p>
                {urlVariables.map(v => (
                  <div key={v} className="flex items-center gap-2">
                    <span className="text-xs font-mono text-muted min-w-[100px]">{'{{'}{v}{'}}'}</span>
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
          </>
        ) : (
          <>
            <div>
              <label className="block text-xs font-medium text-muted mb-1">MCP Transport</label>
              <Select value={mcpTransport} onChange={e => setMcpTransport(e.target.value as 'streamable_http' | 'sse' | 'stdio')} options={MCP_TRANSPORTS} />
            </div>
            {mcpTransport === 'stdio' ? (
              <div>
                <label className="block text-xs font-medium text-muted mb-1">Command *</label>
                <Input value={mcpCommand} onChange={e => setMcpCommand(e.target.value)} placeholder="mcp-server-command" />
              </div>
            ) : (
              <div>
                <label className="block text-xs font-medium text-muted mb-1">Server URL *</label>
                <Input value={mcpServerUrl} onChange={e => setMcpServerUrl(e.target.value)} placeholder="https://mcp.example.com" />
              </div>
            )}
            <div>
              <label className="block text-xs font-medium text-muted mb-1">MCP Tool Name *</label>
              <Input value={mcpToolName} onChange={e => setMcpToolName(e.target.value)} placeholder="weather_current" />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted mb-1">Input Schema JSON</label>
              <Textarea value={mcpSchema} onChange={e => setMcpSchema(e.target.value)} placeholder='{"type":"object","properties":{}}' className="min-h-[100px] font-mono text-xs" />
            </div>
          </>
        )}

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-medium text-muted uppercase tracking-wider">Headers</p>
            <Button type="button" size="sm" variant="ghost" onClick={addHeader}><Plus className="h-3 w-3 mr-1" />Add Header</Button>
          </div>
          {headers.length === 0 ? <p className="text-xs text-muted italic">No headers configured</p> : (
            <div className="space-y-1.5">
              {headers.map(h => (
                <div key={h.id} className="flex items-center gap-1.5">
                  <Input value={h.key} onChange={e => updateHeaderKey(h.id, e.target.value)} placeholder="Key" className="flex-1" />
                  <Input value={h.value} onChange={e => updateHeaderValue(h.id, e.target.value)} placeholder="Value" className="flex-1" />
                  <Button type="button" size="sm" variant="ghost" className="shrink-0 text-red-400 hover:text-red-300" onClick={() => removeHeader(h.id)}><X className="h-3 w-3" /></Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Risk Level</label>
          <Select value={riskLevel} onChange={e => setRiskLevel(e.target.value)} options={RISK_LEVELS} />
        </div>

        {testResult && <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-3"><pre className="text-xs text-green-300 whitespace-pre-wrap font-mono">{testResult}</pre></div>}
        {testError && <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3"><pre className="text-xs text-red-300 whitespace-pre-wrap font-mono">{testError}</pre></div>}

        <div className="flex justify-between gap-2 pt-2 border-t border-border">
          <Button type="button" size="sm" variant="outline" onClick={handleTest} disabled={testTool.isPending}>
            {testTool.isPending ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Play className="h-3 w-3 mr-1" />}
            Test
          </Button>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={handleClose}>Cancel</Button>
            <Button type="submit" loading={createTool.isPending}>Create</Button>
          </div>
        </div>
      </form>
    </Dialog>
  )
}
