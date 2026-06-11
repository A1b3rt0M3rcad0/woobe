import { useState, useMemo, useCallback } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Select } from '@/components/ui/Select'
import { Plus, X } from 'lucide-react'
import { toast } from 'sonner'

interface MockTool {
  id: string
  name: string
  description: string
  type: string
  risk_level: string
  config?: Record<string, unknown>
}

interface CreateToolModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  onCreated: (tool: MockTool) => void
}

const HTTP_METHODS = [
  { value: 'GET', label: 'GET' },
  { value: 'POST', label: 'POST' },
  { value: 'PUT', label: 'PUT' },
  { value: 'PATCH', label: 'PATCH' },
  { value: 'DELETE', label: 'DELETE' },
]

const RISK_LEVELS = [
  { value: 'read_only', label: 'Read Only' },
  { value: 'write', label: 'Write' },
  { value: 'destructive', label: 'Destructive' },
  { value: 'restricted', label: 'Restricted' },
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

export function CreateToolModal({ open, onClose, projectId, agentId, onCreated }: CreateToolModalProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('')
  const [headers, setHeaders] = useState<{ id: string; key: string; value: string }[]>([])
  const [body, setBody] = useState('')
  const [riskLevel, setRiskLevel] = useState('read_only')

  const showBody = ['POST', 'PUT', 'PATCH'].includes(method)

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
    setName('')
    setDescription('')
    setMethod('GET')
    setUrl('')
    setHeaders([])
    setBody('')
    setRiskLevel('read_only')
    setVariableValues({})
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!name.trim()) {
      toast.error('Tool name is required')
      return
    }
    if (!url.trim()) {
      toast.error('URL is required')
      return
    }

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

    const tool: MockTool = {
      id: `tool_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      name: name.trim(),
      description: description.trim(),
      type: 'http_mcp',
      risk_level: riskLevel,
      config,
    }

    onCreated(tool)
    resetForm()
    onClose()
    toast.success(`Tool "${tool.name}" created`)
  }

  const handleClose = () => {
    resetForm()
    onClose()
  }

  return (
    <Dialog open={open} onClose={handleClose} title="Create MCP HTTP Tool">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Name *</label>
          <Input value={name} onChange={e => setName(e.target.value)} placeholder="My HTTP Tool" />
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Description</label>
          <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="Optional description" />
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">HTTP Method</label>
          <Select value={method} onChange={e => setMethod(e.target.value)} options={HTTP_METHODS} />
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
          <Button type="button" variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button type="submit">
            Create
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
