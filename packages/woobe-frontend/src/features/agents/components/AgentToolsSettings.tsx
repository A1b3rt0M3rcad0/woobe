import { useState } from 'react'
import { Link2, Wrench } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { CreateToolModal } from '@/features/playground/components/CreateToolModal'
import { EditToolModal } from '@/features/playground/components/EditToolModal'
import { ImportToolsModal } from '@/features/playground/components/ImportToolsModal'
import { toolPermissionsFromTools, useAgentEditor } from '@/features/playground/AgentEditorContext'
import { AgentToolCard } from '@/features/tools/components/AgentToolCard'
import { isHttpToolGroup } from '@/features/tools/httpToolContract'
import { useTools } from '@/features/tools/hooks'
import type { HttpToolConfig, McpToolPermission, Tool } from '@/features/tools/types'

function initialPermissionsForTool(tool: Tool): Record<string, McpToolPermission> {
  const permissions = { ...(toolPermissionsFromTools([tool])[tool.id] || {}) }
  const config = (tool.config || {}) as HttpToolConfig
  if (!isHttpToolGroup(config)) return permissions
  for (const route of config.routes || []) {
    const mode = route.permission?.mode || route.default_permission || 'review'
    permissions[route.id] = {
      mode: mode === 'allow' || mode === 'deny' || mode === 'review' ? mode : 'review',
      risk_level: route.risk_level,
    }
  }
  return permissions
}

export function AgentToolsSettings({ projectId, agentId }: { projectId: string; agentId: string }) {
  const toolsQuery = useTools(projectId)
  const tools = toolsQuery.data ?? []
  const { state, setField, setState } = useAgentEditor()
  const [createOpen, setCreateOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [editingTool, setEditingTool] = useState<Tool | null>(null)

  const selectedIds = new Set(state.toolIds)
  const selected = state.toolIds.map((id) => tools.find((tool) => tool.id === id)).filter((tool): tool is Tool => Boolean(tool))

  const refreshTools = async () => { await toolsQuery.refetch() }

  const addTool = (tool: Tool) => {
    if (selectedIds.has(tool.id)) return
    const initialPermissions = initialPermissionsForTool(tool)
    setState({
      ...state,
      toolIds: [...state.toolIds, tool.id],
      toolPermissions: { ...state.toolPermissions, [tool.id]: initialPermissions },
    })
    toast.success(`${tool.name} added to the Agent Draft`)
  }

  const removeTool = (tool: Tool) => {
    const permissions = { ...state.toolPermissions }
    delete permissions[tool.id]
    setState({ ...state, toolIds: state.toolIds.filter((id) => id !== tool.id), toolPermissions: permissions })
    toast.success(`${tool.name} removed from the Agent Draft`)
  }

  const updatePermissions = (toolId: string, permissions: Record<string, McpToolPermission>) => {
    setField('toolPermissions', { ...state.toolPermissions, [toolId]: permissions })
  }

  return (
    <div className="p-4">
      <section aria-label="Tools" className="rounded-xl border border-border bg-surface">
        <div className="flex items-center gap-3 p-4"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary-light"><Wrench className="h-4 w-4" /></span><div><p className="text-sm font-semibold">Tools</p><p className="mt-0.5 text-[11px] text-muted">{selected.length} bound to this Draft</p></div></div>
        <div className="border-t border-border p-4">
        <p className="text-xs leading-5 text-muted">Control which Tools this Agent can use.</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Button size="sm" variant="outline" className="h-8 text-[11px]" onClick={() => setImportOpen(true)}><Link2 className="mr-1 h-3.5 w-3.5" />Import</Button>
          <Button size="sm" variant="ghost" className="h-8 text-[11px] text-primary-light" onClick={() => setCreateOpen(true)}>Create</Button>
        </div>
        <p className="mb-2.5 mt-5 text-xs font-semibold uppercase tracking-wider text-muted">Bound tools</p>
      {toolsQuery.isLoading ? (
        <p role="status" className="text-xs text-muted">Loading Tools...</p>
      ) : selected.length === 0 ? (
        <div className="rounded-lg border border-border bg-background/35 p-3">
          <p className="text-xs font-medium">No Tools selected</p>
          <p className="mt-1 text-[11px] text-muted">Create or import Tools for this Agent Draft.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {selected.map((tool) => (
            <AgentToolCard
              key={tool.id}
              context="agent"
              tool={tool}
              onChanged={refreshTools}
              onEdit={() => setEditingTool(tool)}
              onRemove={() => removeTool(tool)}
              permissionOverrides={state.toolPermissions[tool.id] || {}}
              onPermissionOverridesChange={(permissions) => updatePermissions(tool.id, permissions)}
            />
          ))}
        </div>
      )}

      </div>
      </section>
      <ImportToolsModal open={importOpen} onClose={() => setImportOpen(false)} projectId={projectId} importedToolIds={selectedIds} onImport={addTool} />
      <CreateToolModal open={createOpen} onClose={() => setCreateOpen(false)} projectId={projectId} agentId={agentId} onCreated={(tool) => { if (tool) addTool(tool); void refreshTools() }} />
      <EditToolModal tool={editingTool} onClose={() => setEditingTool(null)} onSaved={() => { setEditingTool(null); void refreshTools() }} />
    </div>
  )
}
