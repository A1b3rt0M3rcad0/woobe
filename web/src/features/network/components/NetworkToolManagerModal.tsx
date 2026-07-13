import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Check, Pencil, Plus, Search, Shield, Wrench } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import type { AgentToolPermissions } from '@/features/playground/AgentEditorContext'
import { toolPermissionsFromTools } from '@/features/playground/AgentEditorContext'
import { useCreateTool, useTools, useUpdateTool, useUpdateToolStatus } from '@/features/tools/hooks'
import type { HttpToolConfig, McpToolPermission, Tool } from '@/features/tools/types'
import { cn } from '@/lib/utils'

type Screen = 'tools' | 'create' | 'edit' | 'permissions'

interface Props {
  open: boolean
  projectId: string
  agentId: string
  selectedToolIds: string[]
  toolPermissions: AgentToolPermissions
  initialScreen: Screen
  initialToolId: string | null
  onClose: () => void
  onBindingsChange: (toolIds: string[], permissions: AgentToolPermissions) => void
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function isMcp(tool?: Tool | null) {
  return Boolean(tool && (String(tool.type).toLowerCase() === 'mcp' || recordValue(tool.config).protocol === 'mcp'))
}

function httpConfig(tool?: Tool | null): Partial<HttpToolConfig> {
  return tool && !isMcp(tool) ? tool.config as Partial<HttpToolConfig> : {}
}

export function NetworkToolManagerModal({ open, projectId, agentId, selectedToolIds, toolPermissions, initialScreen, initialToolId, onClose, onBindingsChange }: Props) {
  const toolsQuery = useTools(projectId)
  const createTool = useCreateTool()
  const updateTool = useUpdateTool()
  const updateStatus = useUpdateToolStatus()
  const tools = toolsQuery.data ?? []

  const [screen, setScreen] = useState<Screen>('tools')
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('')
  const [body, setBody] = useState('')
  const [risk, setRisk] = useState('low')
  const [timeoutMs, setTimeoutMs] = useState(30000)
  const [permissions, setPermissions] = useState<Record<string, McpToolPermission>>({})

  const selectedTool = tools.find((item) => item.id === selectedId) || null
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return tools.filter((tool) => !normalized || `${tool.name} ${tool.description || ''} ${tool.type}`.toLowerCase().includes(normalized))
  }, [query, tools])

  useEffect(() => {
    if (!open) return
    setScreen(initialScreen)
    setSelectedId(initialToolId)
    setQuery('')
  }, [initialScreen, initialToolId, open])

  useEffect(() => {
    if (!selectedTool) {
      if (screen === 'create') {
        setName(''); setDescription(''); setMethod('GET'); setUrl(''); setBody(''); setRisk('low'); setTimeoutMs(30000)
      }
      return
    }
    const config = httpConfig(selectedTool)
    setName(selectedTool.name)
    setDescription(selectedTool.description || '')
    setMethod(config.method || 'GET')
    setUrl(config.url || '')
    setBody(typeof config.body === 'string' ? config.body : config.body ? JSON.stringify(config.body, null, 2) : '')
    setRisk(selectedTool.risk_level || 'low')
    setTimeoutMs(selectedTool.timeout_ms || 30000)
    setPermissions(toolPermissions[selectedTool.id] || toolPermissionsFromTools([selectedTool])[selectedTool.id] || {})
  }, [screen, selectedTool?.id])

  const bind = (tool: Tool) => {
    if (selectedToolIds.includes(tool.id)) return
    onBindingsChange([...selectedToolIds, tool.id], { ...toolPermissions, [tool.id]: toolPermissionsFromTools([tool])[tool.id] || {} })
    toast.success(`${tool.name} added to the Agent Draft`)
  }

  const unbind = (tool: Tool) => {
    const next = { ...toolPermissions }
    delete next[tool.id]
    onBindingsChange(selectedToolIds.filter((id) => id !== tool.id), next)
    toast.success(`${tool.name} removed from the Agent Draft`)
  }

  const saveTool = async () => {
    if (!name.trim()) return toast.error('Tool name is required')
    if (!url.trim()) return toast.error('URL is required')
    const config: HttpToolConfig = { protocol: 'http', method, url: url.trim(), headers: [], ...(body.trim() ? { body: body.trim() } : {}), timeout_ms: timeoutMs }
    try {
      const saved = selectedTool
        ? await updateTool.mutateAsync({ toolId: selectedTool.id, data: { name: name.trim(), description: description.trim() || undefined, type: 'http', config, risk_level: risk, timeout_ms: timeoutMs } })
        : await createTool.mutateAsync({ project_id: projectId, agent_id: agentId, name: name.trim(), description: description.trim() || undefined, type: 'http', config, risk_level: risk, timeout_ms: timeoutMs })
      await toolsQuery.refetch()
      if (!selectedTool) bind(saved)
      toast.success(selectedTool ? 'Tool updated' : 'Tool created and added to Draft')
      setScreen('tools')
      setSelectedId(null)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to save Tool') }
  }

  const savePermissions = () => {
    if (!selectedTool) return
    onBindingsChange(selectedToolIds, { ...toolPermissions, [selectedTool.id]: permissions })
    toast.success('Agent Tool permissions updated')
    setScreen('tools')
  }

  const toggleGlobalStatus = async (tool: Tool) => {
    try {
      await updateStatus.mutateAsync({ toolId: tool.id, data: { status: tool.status === 'active' ? 'inactive' : 'active' } })
      await toolsQuery.refetch()
      toast.success(`Tool ${tool.status === 'active' ? 'deactivated' : 'activated'} globally`)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to update Tool status') }
  }

  const discovered = selectedTool && isMcp(selectedTool) && Array.isArray(recordValue(selectedTool.config).discovered_tools)
    ? recordValue(selectedTool.config).discovered_tools as Array<Record<string, unknown>>
    : []

  return (
    <Dialog open={open} onClose={onClose} title="Manage Tools" className="max-w-5xl overflow-hidden bg-surface/95">
      <div className="-m-6 flex h-[74vh] min-h-[560px] flex-col overflow-hidden">
        {screen === 'tools' ? <>
          <div className="flex shrink-0 gap-3 border-b border-border/80 p-4"><div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search Tools..." className="pl-9" /></div><Button size="sm" onClick={() => { setSelectedId(null); setScreen('create') }}><Plus className="mr-2 h-3.5 w-3.5" />Create Tool</Button></div>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-4">{filtered.length === 0 ? <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">No Tools found.</div> : <div className="grid gap-3 sm:grid-cols-2">{filtered.map((tool) => {
            const bound = selectedToolIds.includes(tool.id)
            return <article key={tool.id} className={cn('rounded-xl border p-4', bound ? 'border-primary/40 bg-primary/[0.05]' : 'border-border/80 bg-background/50')}><div className="flex items-start gap-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface"><Wrench className="h-4 w-4 text-primary-light" /></div><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate text-sm font-medium text-white">{tool.name}</p>{bound ? <Check className="h-3.5 w-3.5 text-primary-light" /> : null}</div><p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{tool.description || 'No description'}</p><p className="mt-2 text-[10px] uppercase text-muted">{isMcp(tool) ? 'MCP' : String(tool.type).toUpperCase()} · {tool.status} · {tool.risk_level} risk</p></div></div><div className="mt-3 flex flex-wrap justify-end gap-2 border-t border-border/70 pt-3">{isMcp(tool) && bound ? <Button size="sm" variant="ghost" onClick={() => { setSelectedId(tool.id); setScreen('permissions') }}><Shield className="mr-1 h-3.5 w-3.5" />Permissions</Button> : null}{!isMcp(tool) ? <Button size="sm" variant="ghost" onClick={() => { setSelectedId(tool.id); setScreen('edit') }}><Pencil className="mr-1 h-3.5 w-3.5" />Edit</Button> : null}<Button size="sm" variant="ghost" onClick={() => void toggleGlobalStatus(tool)}>{tool.status === 'active' ? 'Deactivate' : 'Activate'}</Button><Button size="sm" variant={bound ? 'outline' : 'default'} onClick={() => bound ? unbind(tool) : bind(tool)}>{bound ? 'Remove from Agent' : 'Add to Draft'}</Button></div></article>
          })}</div>}</div>
        </> : screen === 'permissions' && selectedTool ? <>
          <div className="flex shrink-0 items-center gap-3 border-b border-border/80 p-4"><Button size="sm" variant="ghost" onClick={() => setScreen('tools')}><ArrowLeft className="mr-2 h-3.5 w-3.5" />Tools</Button><div><p className="text-sm font-medium text-white">{selectedTool.name}</p><p className="text-xs text-muted">Permissions for this Agent Draft only.</p></div></div>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5">{discovered.length === 0 ? <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">No discovered MCP Tools.</div> : <div className="space-y-2">{discovered.map((remote) => { const remoteName = String(remote.name || 'tool'); const permission = permissions[remoteName]?.mode || 'review'; return <div key={remoteName} className="flex items-start gap-3 rounded-xl border border-border/80 bg-background/50 p-3"><div className="min-w-0 flex-1"><p className="text-xs font-medium text-white">{String(remote.title || remoteName)}</p><p className="mt-1 text-[10px] text-muted">{String(remote.description || remoteName)}</p></div><Select className="w-32" value={permission} onChange={(event) => setPermissions((previous) => ({ ...previous, [remoteName]: { ...previous[remoteName], mode: event.target.value as McpToolPermission['mode'] } }))} options={[{ value: 'allow', label: 'Allow' }, { value: 'review', label: 'Review' }, { value: 'deny', label: 'Deny' }]} /></div> })}</div>}</div>
          <div className="flex shrink-0 justify-end gap-2 border-t border-border/80 p-4"><Button variant="outline" onClick={() => setScreen('tools')}>Cancel</Button><Button onClick={savePermissions}>Save permissions</Button></div>
        </> : <>
          <div className="flex shrink-0 items-center gap-3 border-b border-border/80 p-4"><Button size="sm" variant="ghost" onClick={() => setScreen('tools')}><ArrowLeft className="mr-2 h-3.5 w-3.5" />Tools</Button><div><p className="text-sm font-medium text-white">{screen === 'edit' ? 'Edit HTTP Tool' : 'Create HTTP Tool'}</p><p className="text-xs text-muted">The Tool remains a Project resource; the binding belongs to this Draft.</p></div></div>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5"><div className="mx-auto max-w-3xl space-y-4"><div className="grid gap-4 sm:grid-cols-2"><label className="text-xs font-medium text-muted">Name<Input className="mt-1.5" value={name} onChange={(event) => setName(event.target.value)} /></label><label className="text-xs font-medium text-muted">Risk<Select className="mt-1.5" value={risk} onChange={(event) => setRisk(event.target.value)} options={[{ value: 'low', label: 'Low' }, { value: 'medium', label: 'Medium' }, { value: 'high', label: 'High' }, { value: 'critical', label: 'Critical' }]} /></label></div><label className="block text-xs font-medium text-muted">Description<Input className="mt-1.5" value={description} onChange={(event) => setDescription(event.target.value)} /></label><div className="grid gap-4 sm:grid-cols-[140px_1fr]"><label className="text-xs font-medium text-muted">Method<Select className="mt-1.5" value={method} onChange={(event) => setMethod(event.target.value)} options={['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((value) => ({ value, label: value }))} /></label><label className="text-xs font-medium text-muted">URL<Input className="mt-1.5 font-mono" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://api.example.com/resource" /></label></div>{['POST', 'PUT', 'PATCH'].includes(method) ? <label className="block text-xs font-medium text-muted">Body<Textarea className="mt-1.5 min-h-[150px] font-mono text-xs" value={body} onChange={(event) => setBody(event.target.value)} placeholder='{ "query": "{{query}}" }' /></label> : null}<label className="block max-w-xs text-xs font-medium text-muted">Timeout (ms)<Input type="number" min="100" className="mt-1.5" value={timeoutMs} onChange={(event) => setTimeoutMs(Number(event.target.value) || 30000)} /></label></div></div>
          <div className="flex shrink-0 justify-end gap-2 border-t border-border/80 p-4"><Button variant="outline" onClick={() => setScreen('tools')}>Cancel</Button><Button onClick={() => void saveTool()} loading={createTool.isPending || updateTool.isPending}>{screen === 'edit' ? 'Save Tool' : 'Create and add to Draft'}</Button></div>
        </>}
      </div>
    </Dialog>
  )
}
