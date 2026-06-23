import { useState } from 'react'
import type { FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { toast } from 'sonner'
import type { CreateToolRequest, HttpToolConfig, McpToolConfig, ToolConfig, ToolProtocol } from '@/features/tools/types'

export type ApiFirstToolFormSubmitValue = Omit<CreateToolRequest, 'project_id'>

type Protocol = 'http' | 'mcp'

interface ApiFirstToolFormProps {
  submitLabel?: string
  cancelLabel?: string
  loading?: boolean
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
]

const RISKS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
]

function serverName(value: string): string {
  try {
    return `MCP ${new URL(value).hostname}`
  } catch {
    return 'MCP Server'
  }
}

export function ApiFirstToolForm({ submitLabel = 'Create', cancelLabel = 'Cancel', loading = false, onSubmit, onCancel }: ApiFirstToolFormProps) {
  const [protocol, setProtocol] = useState<Protocol>('http')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [riskLevel, setRiskLevel] = useState('low')
  const [timeoutMs, setTimeoutMs] = useState(30000)
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('')
  const [body, setBody] = useState('')
  const [mcpUrl, setMcpUrl] = useState('')

  const reset = () => {
    setProtocol('http')
    setName('')
    setDescription('')
    setRiskLevel('low')
    setTimeoutMs(30000)
    setMethod('GET')
    setUrl('')
    setBody('')
    setMcpUrl('')
  }

  const buildConfig = (): ToolConfig => {
    if (protocol === 'mcp') {
      const config: McpToolConfig = {
        protocol: 'mcp',
        mode: 'server',
        exposure: 'all_discovered',
        server: { transport: 'streamable_http', url: mcpUrl.trim(), headers: [] },
        discovered_tools: [],
        discovery_cache_ttl_seconds: 3600,
        timeout_ms: timeoutMs,
      }
      return config
    }
    const config: HttpToolConfig = { protocol: 'http', method, url: url.trim(), headers: [], timeout_ms: timeoutMs }
    if (['POST', 'PUT', 'PATCH'].includes(method) && body.trim()) config.body = body.trim()
    return config
  }

  const validate = () => {
    if (protocol === 'http' && !url.trim()) return 'URL is required'
    if (protocol === 'mcp' && !mcpUrl.trim()) return 'MCP server URL is required'
    return null
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const error = validate()
    if (error) {
      toast.error(error)
      return
    }
    const resolvedName = name.trim() || (protocol === 'mcp' ? serverName(mcpUrl.trim()) : 'HTTP Tool')
    await onSubmit({
      name: resolvedName,
      description: description.trim() || (protocol === 'mcp' ? 'MCP provider saved. Use Connect from the Tools page before enabling tools.' : undefined),
      type: protocol as ToolProtocol,
      config: buildConfig(),
      risk_level: riskLevel,
      timeout_ms: timeoutMs,
    })
    reset()
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="grid gap-3 md:grid-cols-2">
        <div><label className="mb-1 block text-xs font-medium text-muted">Runtime</label><Select value={protocol} onChange={(event) => setProtocol(event.target.value as Protocol)} options={PROTOCOLS} /></div>
        <div><label className="mb-1 block text-xs font-medium text-muted">Risk Level</label><Select value={riskLevel} onChange={(event) => setRiskLevel(event.target.value)} options={RISKS} /></div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div><label className="mb-1 block text-xs font-medium text-muted">Display name</label><Input value={name} onChange={(event) => setName(event.target.value)} placeholder={protocol === 'mcp' ? 'Auto-filled from URL' : 'Fetch Customer'} /></div>
        <div><label className="mb-1 block text-xs font-medium text-muted">Timeout (ms)</label><Input type="number" value={timeoutMs} min={1000} max={120000} onChange={(event) => setTimeoutMs(Number(event.target.value))} /></div>
      </div>

      <div><label className="mb-1 block text-xs font-medium text-muted">Description</label><Input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What this tool provider does" /></div>

      {protocol === 'http' ? (
        <div className="space-y-3 rounded-2xl border border-border/80 bg-card/40 p-4">
          <div className="grid gap-3 md:grid-cols-[1fr_130px]"><div><label className="mb-1 block text-xs font-medium text-muted">URL *</label><Input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://api.example.com/items" /></div><div><label className="mb-1 block text-xs font-medium text-muted">Method</label><Select value={method} onChange={(event) => setMethod(event.target.value)} options={METHODS} /></div></div>
          {['POST', 'PUT', 'PATCH'].includes(method) ? <div><label className="mb-1 block text-xs font-medium text-muted">Body</label><Textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder='{"key":"value"}' className="min-h-[90px] font-mono text-xs" /></div> : null}
        </div>
      ) : (
        <div className="space-y-3 rounded-2xl border border-border/80 bg-card/40 p-4">
          <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-3 text-xs text-muted">Save this MCP provider first. Then use Connect from the Tools page.</div>
          <div><label className="mb-1 block text-xs font-medium text-muted">MCP Server URL *</label><Input value={mcpUrl} onChange={(event) => setMcpUrl(event.target.value)} placeholder="https://mcp.example.com" /></div>
        </div>
      )}

      <div className="flex flex-col justify-end gap-2 border-t border-border pt-2 sm:flex-row"><Button type="button" variant="outline" onClick={onCancel}>{cancelLabel}</Button><Button type="submit" loading={loading}>{submitLabel}</Button></div>
    </form>
  )
}
