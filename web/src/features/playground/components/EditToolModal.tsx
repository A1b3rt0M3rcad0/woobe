import { useState, useMemo, useCallback, useEffect } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Select } from '@/components/ui/Select'
import { Plus, X, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useUpdateTool } from '@/features/tools/hooks'
import type { Tool } from '@/features/tools/types'

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

  const showBody = ['POST', 'PUT', 'PATCH'].includes(method)

  const urlVariables = useMemo(() => extractUrlVariables(url), [url])
  const [variableValues, setVariableValues] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!tool) return
    setName(tool.name)
    setDescription(tool.description || '')
    const config = tool.config || {}
    setMethod((config.method as string) || 'GET')
    setUrl((config.url as string) || '')
    const rawHeaders = (config.headers as Array<{ key: string; value: string }>) || []
    setHeaders(rawHeaders.map(h => ({ id: headerId(), key: h.key, value: h.value })))
    setBody((config.body as string) || '')
    setRiskLevel(tool.risk_level || 'low')
    setTimeoutMs(tool.timeout_ms || 30000)
    const vars = (config.variables as Record<string, string>) || {}
    setVariableValues(vars)
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

  const buildConfig = () => {
    const config: Record<string, unknown> = {
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
    if (!url.trim()) {
      toast.error('URL is required')
      return
    }

    const config = buildConfig()

    try {
      await updateTool.mutateAsync({
        toolId: tool.id,
        data: {
          name: name.trim(),
          description: description.trim() || undefined,
          config,
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
    <Dialog open={tool !== null} onClose={onClose} title={`Edit Tool: ${tool?.name || ''}`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Name *</label>
          <Input value={name} onChange={e => setName(e.target.value)} placeholder="My HTTP Tool" />
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Description</label>
          <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="Optional description" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-muted mb-1">HTTP Method</label>
            <Select value={method} onChange={e => setMethod(e.target.value)} options={HTTP_METHODS} />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Timeout (ms)</label>
            <Input type="number" value={timeoutMs} onChange={e => setTimeoutMs(Number(e.target.value))} min={1000} max={120000} />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">URL *</label>
          <Input
            value={url}
            onChange={e => handleUrlChange(e.target.value)}
            placeholder="https://api.example.com/users/{{userId}}"
          />
          <p className="text-[10px] text-muted mt-1">
            Use {'{{variableName}}'} for dynamic values in the URL
          </p>
        </div>

        {urlVariables.length > 0 && (
          <div className="rounded-lg border border-border bg-background p-3 space-y-2">
            <p className="text-[10px] font-medium text-muted uppercase tracking-wider">URL Variables</p>
            {urlVariables.map(v => (
              <div key={v} className="flex items-center gap-2">
                <span className="text-xs font-mono text-muted min-w-[100px]">{'{{'}{v}{'}}'}</span>
                <Input
                  value={variableValues[v] || ''}
                  onChange={e => setVariableValues(prev => ({ ...prev, [v]: e.target.value }))}
                  placeholder={`Default value for ${v}`}
                  className="flex-1"
                />
              </div>
            ))}
          </div>
        )}

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-medium text-muted uppercase tracking-wider">Headers</p>
            <Button type="button" size="sm" variant="ghost" onClick={addHeader}>
              <Plus className="h-3 w-3 mr-1" />
              Add Header
            </Button>
          </div>
          {headers.length === 0 ? (
            <p className="text-xs text-muted italic">No headers configured</p>
          ) : (
            <div className="space-y-1.5">
              {headers.map(h => (
                <div key={h.id} className="flex items-center gap-1.5">
                  <Input
                    value={h.key}
                    onChange={e => updateHeaderKey(h.id, e.target.value)}
                    placeholder="Key"
                    className="flex-1"
                  />
                  <Input
                    value={h.value}
                    onChange={e => updateHeaderValue(h.id, e.target.value)}
                    placeholder="Value"
                    className="flex-1"
                  />
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
            <label className="block text-xs font-medium text-muted mb-1">Body</label>
            <Textarea
              value={body}
              onChange={e => setBody(e.target.value)}
              placeholder='{"key": "value"}'
              className="min-h-[100px] font-mono text-xs"
            />
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Risk Level</label>
          <Select value={riskLevel} onChange={e => setRiskLevel(e.target.value)} options={RISK_LEVELS} />
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={updateTool.isPending}>
            Save
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
