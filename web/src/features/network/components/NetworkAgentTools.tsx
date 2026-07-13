import { useState } from 'react'
import { Plus, Wrench } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { useTools } from '@/features/tools/hooks'
import type { Tool } from '@/features/tools/types'
import { NetworkToolManagerModal } from './NetworkToolManagerModal'

type Screen = 'tools' | 'create' | 'edit' | 'permissions'
function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}
function typeLabel(tool: Tool) {
  return String(tool.type).toLowerCase() === 'mcp' || record(tool.config).protocol === 'mcp' ? 'MCP' : String(tool.type || 'HTTP').toUpperCase()
}

export function NetworkAgentTools({ projectId, agentId }: { projectId: string; agentId: string }) {
  const toolsQuery = useTools(projectId)
  const tools = toolsQuery.data ?? []
  const { state, setState } = useAgentEditor()
  const [manager, setManager] = useState<{ open: boolean; screen: Screen; toolId: string | null }>({ open: false, screen: 'tools', toolId: null })
  const selected = state.toolIds.map((id) => tools.find((tool) => tool.id === id)).filter((tool): tool is Tool => Boolean(tool))
  const remove = (tool: Tool) => { const permissions = { ...state.toolPermissions }; delete permissions[tool.id]; setState({ ...state, toolIds: state.toolIds.filter((id) => id !== tool.id), toolPermissions: permissions }); toast.success(`${tool.name} removed from the Agent Draft`) }
  return <div className="space-y-3 p-4">
    <div className="flex items-center justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wider text-muted">Tools</p>{selected.length ? <p className="mt-0.5 text-[10px] text-muted">{selected.length} bound to this Draft</p> : null}</div><div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => setManager({ open: true, screen: 'create', toolId: null })}><Plus className="mr-1 h-3.5 w-3.5" />Create</Button><Button size="sm" onClick={() => setManager({ open: true, screen: 'tools', toolId: null })}>Import</Button></div></div>
    {toolsQuery.isLoading ? <p className="text-xs text-muted">Loading Tools...</p> : selected.length === 0 ? <div className="rounded-xl border border-dashed border-border bg-surface p-6 text-center"><Wrench className="mx-auto h-5 w-5 text-muted" /><p className="mt-4 text-sm font-medium text-white">No Tools selected</p><p className="mt-1 text-xs text-muted">Create or import Tools for this Agent Draft.</p><div className="mt-4 flex justify-center gap-2"><Button size="sm" onClick={() => setManager({ open: true, screen: 'create', toolId: null })}>Create Tool</Button><Button size="sm" variant="outline" onClick={() => setManager({ open: true, screen: 'tools', toolId: null })}>Import Tool</Button></div></div> : <div className="space-y-3">{selected.map((tool) => { const mcp = typeLabel(tool) === 'MCP'; const discovered = Array.isArray(record(tool.config).discovered_tools) ? record(tool.config).discovered_tools as unknown[] : []; const allowed = Object.values(state.toolPermissions[tool.id] || {}).filter((item) => item.mode === 'allow').length; return <article key={tool.id} className="rounded-xl border border-border bg-surface p-3"><div className="flex items-start gap-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background"><Wrench className="h-4 w-4 text-primary-light" /></div><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate text-sm font-medium text-white">{tool.name}</p><Badge variant={tool.status === 'active' ? 'success' : 'secondary'}>{tool.status}</Badge></div><p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{tool.description || 'No description'}</p><p className="mt-2 text-[10px] text-muted">{typeLabel(tool)} · {tool.risk_level} risk{mcp ? ` · ${allowed}/${discovered.length} allowed` : ''}</p></div></div><div className="mt-3 flex justify-end gap-2 border-t border-border/80 pt-3">{mcp ? <Button size="sm" variant="ghost" onClick={() => setManager({ open: true, screen: 'permissions', toolId: tool.id })}>Permissions</Button> : null}{!mcp ? <Button size="sm" variant="ghost" onClick={() => setManager({ open: true, screen: 'edit', toolId: tool.id })}>Edit</Button> : null}<Button size="sm" variant="outline" onClick={() => remove(tool)}>Remove</Button></div></article> })}</div>}
    <NetworkToolManagerModal open={manager.open} projectId={projectId} agentId={agentId} selectedToolIds={state.toolIds} toolPermissions={state.toolPermissions} initialScreen={manager.screen} initialToolId={manager.toolId} onClose={() => setManager({ open: false, screen: 'tools', toolId: null })} onBindingsChange={(toolIds, permissions) => setState({ ...state, toolIds, toolPermissions: permissions })} />
  </div>
}
