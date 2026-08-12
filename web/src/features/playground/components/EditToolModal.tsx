import { useEffect, useState } from 'react'
import { Plus, Wrench, X } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { inspectHttpToolContract, isHttpToolGroup } from '@/features/tools/httpToolContract'
import { useUpdateTool } from '@/features/tools/hooks'
import type { HttpHeader, HttpToolConfig, Tool } from '@/features/tools/types'
import { EditHttpGroupModal } from './EditHttpGroupModal'

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

let nextHeaderId = 1
function headerId() {
  nextHeaderId += 1
  return `header_${nextHeaderId}`
}

type HeaderDraft = HttpHeader & { id: string }

function isGroupedHttpTool(tool: Tool | null): tool is Tool {
  if (!tool || tool.type === 'mcp') return false
  return isHttpToolGroup((tool.config || {}) as HttpToolConfig)
}

export function EditToolModal(props: EditToolModalProps) {
  if (isGroupedHttpTool(props.tool)) {
    return <EditHttpGroupModal tool={props.tool} onClose={props.onClose} onSaved={props.onSaved} />
  }
  return <LegacyToolEditor {...props} />
}

function LegacyToolEditor({ tool, onClose, onSaved }: EditToolModalProps) {
  const updateTool = useUpdateTool()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [riskLevel, setRiskLevel] = useState('low')
  const [timeoutMs, setTimeoutMs] = useState(30000)
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('')
  const [body, setBody] = useState('')
  const [headers, setHeaders] = useState<HeaderDraft[]>([])

  const isMcp = tool?.type === 'mcp'
  const showBody = !isMcp && !['GET', 'HEAD'].includes(method)

  useEffect(() => {
    if (!tool) return
    setName(tool.name)
    setDescription(tool.description || '')
    setRiskLevel(tool.risk_level || 'low')
    setTimeoutMs(tool.timeout_ms || 30000)
    if (tool.type === 'mcp') return
    const config = (tool.config || {}) as HttpToolConfig
    setMethod(config.method || 'GET')
    setUrl(config.url || '')
    setBody(typeof config.body === 'string' ? config.body : config.body ? JSON.stringify(config.body, null, 2) : '')
    setHeaders((config.headers || []).map((header) => ({ ...header, id: headerId() })))
  }, [tool])

  const addHeader = () => setHeaders((current) => [...current, { id: headerId(), key: '', value: '' }])
  const updateHeader = (id: string, field: 'key' | 'value', value: string) => {
    setHeaders((current) => current.map((header) => header.id === id ? { ...header, [field]: value } : header))
  }
  const removeHeader = (id: string) => setHeaders((current) => current.filter((header) => header.id !== id))

  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!tool || !name.trim()) {
      toast.error('Tool name is required')
      return
    }

    let config: HttpToolConfig | undefined
    let inputSchema = tool.input_schema
    if (!isMcp) {
      if (!url.trim()) {
        toast.error('URL is required')
        return
      }
      config = {
        protocol: 'http',
        mode: 'single',
        method,
        url: url.trim(),
        headers: headers
          .filter((header) => header.key.trim())
          .map(({ id: _id, ...header }) => ({ ...header, key: header.key.trim() })),
        ...(showBody && body.trim() ? { body: body.trim() } : {}),
        timeout_ms: timeoutMs,
      }
      const contract = inspectHttpToolContract(config, tool.input_schema)
      if (contract.errors.length) {
        toast.error(contract.errors[0])
        return
      }
      inputSchema = contract.inputSchema
    }

    try {
      await updateTool.mutateAsync({
        toolId: tool.id,
        data: {
          name: name.trim(),
          description: description.trim() || undefined,
          risk_level: riskLevel,
          timeout_ms: timeoutMs,
          ...(config ? { type: 'http', config, input_schema: inputSchema } : {}),
        },
      })
      toast.success(`Tool "${name.trim()}" updated`)
      onSaved()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Tool')
    }
  }

  return (
    <Dialog open={tool !== null} onClose={onClose} title={`Edit Tool${tool?.name ? `: ${tool.name}` : ''}`} className="max-w-4xl bg-surface/95">
      <form onSubmit={save} className="space-y-5">
        <div className="flex items-center gap-3 rounded-xl border border-border/80 bg-background/40 p-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary-light"><Wrench className="h-4 w-4" /></span>
          <div><p className="text-sm font-semibold text-white">{isMcp ? 'MCP provider metadata' : 'Legacy HTTP Tool'}</p><p className="mt-0.5 text-xs text-muted">{isMcp ? 'Connection and discovered tools remain managed by the MCP panel.' : 'Existing single-route Tools remain compatible. New HTTP APIs use grouped routes.'}</p></div>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div><label className="mb-1 block text-xs font-medium text-muted">Name *</label><Input value={name} onChange={(event) => setName(event.target.value)} /></div>
          <div><label className="mb-1 block text-xs font-medium text-muted">Risk</label><Select value={riskLevel} onChange={(event) => setRiskLevel(event.target.value)} options={RISK_LEVELS} /></div>
          <div><label className="mb-1 block text-xs font-medium text-muted">Description</label><Input value={description} onChange={(event) => setDescription(event.target.value)} /></div>
          <div><label className="mb-1 block text-xs font-medium text-muted">Timeout (ms)</label><Input type="number" min={1000} max={120000} value={timeoutMs} onChange={(event) => setTimeoutMs(Number(event.target.value))} /></div>
        </div>

        {!isMcp ? (
          <div className="space-y-4 rounded-xl border border-border/80 bg-background/40 p-4">
            <div className="grid gap-3 md:grid-cols-[140px_minmax(0,1fr)]">
              <div><label className="mb-1 block text-xs font-medium text-muted">Method</label><Select value={method} onChange={(event) => setMethod(event.target.value)} options={HTTP_METHODS} /></div>
              <div><label className="mb-1 block text-xs font-medium text-muted">URL *</label><Input value={url} onChange={(event) => setUrl(event.target.value)} className="font-mono text-xs" /></div>
            </div>
            <div className="space-y-2 rounded-lg border border-border/70 p-3">
              <div className="flex items-center justify-between"><p className="text-xs font-medium text-white">Headers</p><Button type="button" size="sm" variant="ghost" onClick={addHeader}><Plus className="mr-1 h-3 w-3" />Add</Button></div>
              {headers.map((header) => <div key={header.id} className="grid gap-2 md:grid-cols-[1fr_1fr_32px]"><Input value={header.key} onChange={(event) => updateHeader(header.id, 'key', event.target.value)} placeholder="Name" /><Input value={header.value} onChange={(event) => updateHeader(header.id, 'value', event.target.value)} placeholder="Value" /><Button type="button" size="sm" variant="ghost" className="text-red-300" onClick={() => removeHeader(header.id)}><X className="h-3.5 w-3.5" /></Button></div>)}
            </div>
            {showBody ? <div><label className="mb-1 block text-xs font-medium text-muted">Body</label><Textarea value={body} onChange={(event) => setBody(event.target.value)} className="min-h-[140px] font-mono text-xs" /></div> : null}
          </div>
        ) : null}

        <div className="flex justify-end gap-2 border-t border-border pt-4"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" loading={updateTool.isPending}>Save</Button></div>
      </form>
    </Dialog>
  )
}
