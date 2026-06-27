import { useState, useMemo, useCallback, useEffect } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Select } from '@/components/ui/Select'
import { Plus, X, Wrench } from 'lucide-react'
import { toast } from 'sonner'
import { useUpdateTool } from '@/features/tools/hooks'
import type { HttpToolConfig, Tool } from '@/features/tools/types'

interface EditToolModalProps {
  tool: Tool | null
  onClose: () => void
  onSaved: () => void
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

function asHttpConfig(tool: Tool | null): Partial<HttpToolConfig> {
  if (!tool || tool.type === 'mcp') return {}
  return (tool.config || {}) as Partial<HttpToolConfig>
}

function bodyToText(body: HttpToolConfig['body']): string {
  if (!body) return ''
  if (typeof body === 'string') return body
  return JSON.stringify(body, null, 2)
}

let nextId = 1
function headerId() {
  return `hdr_${nextId++}`
}

export function EditToolModal({ tool, onClose, onSaved }: EditToolModalProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('')
  const [headers, setHeaders] = useState<{ id: string; key: string; value: string }[]>([])
  const [body, setBody] = useState('')
  const [riskLevel, setRiskLevel] = useState('low')
  const [timeoutMs, setTimeoutMs] = useState(30000)

  const updateTool = useUpdateTool()
  const isMcpTool = tool?.type === 'mcp'
  const canEditHttpConfig = Boolean(tool && !isMcpTool)
  const showBody = canEditHttpConfig && ['POST', 'PUT', 'PATCH'].includes(method)

  const urlVariables = useMemo(() => extractUrlVariables(url), [url])
  const [variableValues, setVariableValues] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!tool) return
    setName(tool.name)
    setDescription(tool.description || '')
    setRiskLevel(tool.risk_level || 'low')
    setTimeoutMs(tool.timeout_ms || 30000)

    const config = asHttpConfig(tool)
    setMethod(config.method || 'GET')
    setUrl(config.url || '')
    const rawHeaders = Array.isArray(config.headers) ? config.headers : []
    setHeaders(rawHeaders.map(h => ({ id: headerId(), key: h.key, value: h.value })))
    setBody(bodyToText(config.body))
    setVariableValues(config.variables || {})
  }, [tool])

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

  const buildHttpConfig = (): HttpToolConfig => {
    const config: HttpToolConfig = {
      protocol: 'http',
      url: url.trim(),
      method,
      headers: headers.filter(h => h.key.trim()).map(h => ({ key: h.key.trim(), value: h.value })),
    }
    if (showBody && body.trim()) {
      config.body = body.trim()
    }
    if (urlVariables.length > 0) {
      config.variables = urlVariables.reduce<Record<string, string>>((acc, v) => {
        acc[v] = variableValues[v] || ''
        return acc
      }, {})
    }
    return config
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!tool) return

    if (!name.trim()) {
      toast.error('Tool name is required')
      return
    }
    if (canEditHttpConfig && !url.trim()) {
      toast.error('URL is required')
      return
    }

    try {
      await updateTool.mutateAsync({
        toolId: tool.id,
        data: {
          name: name.trim(),
          description: description.trim() || undefined,
          ...(canEditHttpConfig ? { type: 'http', config: buildHttpConfig() } : {}),
          risk_level: riskLevel,
          timeout_ms: timeoutMs,
        },
      })
      toast.success(`Tool "${name.trim()}" updated`)
      onSaved()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update tool')
    }
  }

  return (
    <Dialog open={tool !== null} onClose={onClose} title={`Edit Tool${tool?.name ? `: ${tool.name}` : ''}`} className="max-w-5xl overflow-hidden bg-surface/95">
      <form onSubmit={handleSubmit} className="grid max-h-[72vh] grid-cols-[300px_1fr] gap-0 overflow-hidden -m-6">
        <aside className="border-r border-border/90 bg-background/25 p-5">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">
              <Wrench className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">{tool?.name || 'Tool'}</p>
              <p className="text-[11px] text-muted">{isMcpTool ? 'MCP provider metadata' : 'HTTP tool configuration'}</p>
            </div>
          </div>

          {isMcpTool && (
            <div className="mt-4 rounded-xl border border-blue-500/30 bg-blue-500/5 p-3">
              <p className="text-xs font-medium text-blue-300">MCP tool</p>
              <p className="mt-1 text-xs leading-relaxed text-muted">This modal edits shared metadata. Server connection and discovered tool permissions are managed from the MCP tools panel.</p>
            </div>
          )}

          <div className="mt-4 space-y-3 rounded-xl border border-border/80 bg-background/45 p-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">Name *</label>
              <Input value={name} onChange={e => setName(e.target.value)} placeholder={isMcpTool ? 'My MCP Tool' : 'My HTTP Tool'} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">Description</label>
              <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="Optional description" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">Risk Level</label>
              <Select value={riskLevel} onChange={e => setRiskLevel(e.target.value)} options={RISK_LEVELS} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted">Timeout (ms)</label>
              <Input type="number" value={timeoutMs} onChange={e => setTimeoutMs(Number(e.target.value))} min={1000} max={120000} />
            </div>
          </div>
        </aside>

        <section className="flex min-h-0 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {canEditHttpConfig ? (
              <div className="space-y-4">
                <div className="grid grid-cols-[1fr_140px] gap-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted">URL *</label>
                    <Input value={url} onChange={e => handleUrlChange(e.target.value)} placeholder="https://api.example.com/users/{{userId}}" />
                    <p className="mt-1 text-[10px] text-muted">Use {'{{variableName}}'} for dynamic values in the URL.</p>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted">HTTP Method</label>
                    <Select value={method} onChange={e => setMethod(e.target.value)} options={HTTP_METHODS} />
                  </div>
                </div>

                {urlVariables.length > 0 && (
                  <div className="rounded-xl border border-border/80 bg-background/45 p-3 space-y-2">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">URL Variables</p>
                    {urlVariables.map(v => (
                      <div key={v} className="flex items-center gap-2">
                        <span className="min-w-[100px] text-xs font-mono text-muted">{'{{'}{v}{'}}'}</span>
                        <Input value={variableValues[v] || ''} onChange={e => setVariableValues(prev => ({ ...prev, [v]: e.target.value }))} placeholder={`Default value for ${v}`} className="flex-1" />
                      </div>
                    ))}
                  </div>
                )}

                <div className="space-y-2 rounded-xl border border-border/80 bg-background/45 p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Headers</p>
                    <Button type="button" size="sm" variant="ghost" onClick={addHeader}>
                      <Plus className="h-3 w-3 mr-1" />
                      Add Header
                    </Button>
                  </div>
                  {headers.length === 0 ? (
                    <p className="text-xs italic text-muted">No headers configured</p>
                  ) : (
                    <div className="space-y-1.5">
                      {headers.map(h => (
                        <div key={h.id} className="flex items-center gap-1.5">
                          <Input value={h.key} onChange={e => updateHeaderKey(h.id, e.target.value)} placeholder="Key" className="flex-1" />
                          <Input value={h.value} onChange={e => updateHeaderValue(h.id, e.target.value)} placeholder="Value" className="flex-1" />
                          <Button type="button" size="sm" variant="ghost" className="shrink-0 text-red-400 hover:text-red-300" onClick={() => removeHeader(h.id)}>
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {showBody && (
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted">Body</label>
                    <Textarea value={body} onChange={e => setBody(e.target.value)} placeholder='{"key": "value"}' className="min-h-[140px] font-mono text-xs" />
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-xl border border-border/80 bg-background/45 p-4 text-sm text-muted">
                MCP provider server configuration is not edited in this HTTP form. Use Manage tools to control discovered remote tool permissions.
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 border-t border-border/90 bg-background/20 p-4">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={updateTool.isPending}>Save</Button>
          </div>
        </section>
      </form>
    </Dialog>
  )
}
