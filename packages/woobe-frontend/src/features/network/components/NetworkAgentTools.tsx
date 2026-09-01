import { useState } from 'react'
import { Link2, Plus, Wrench } from 'lucide-react'
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

export function NetworkAgentTools({ projectId, agentId }: { projectId: string; agentId: string }) {
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
    <div className="space-y-3 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Tools</p>
          {selected.length ? <p className="mt-0.5 text-[10px] text-muted">{selected.length} bound to this Draft</p> : null}
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setCreateOpen(true)}><Plus className="mr-1 h-3.5 w-3.5" />Create</Button>
          <Button size="sm" onClick={() => setImportOpen(true)}><Link2 className="mr-1 h-3.5 w-3.5" />Import</Button>
        </div>
      </div>

      {toolsQuery.isLoading ? (
        <p className="text-xs text-muted">Loading Tools...</p>
      ) : selected.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-surface p-6 text-center">
          <Wrench className="mx-auto h-5 w-5 text-muted" />
          <p className="mt-4 text-sm font-medium text-white">No Tools selected</p>
          <p className="mt-1 text-xs text-muted">Create or import Tools for this Agent Draft.</p>
          <div className="mt-4 flex justify-center gap-2">
            <Button size="sm" onClick={() => setCreateOpen(true)}>Create Tool</Button>
            <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}>Import Tool</Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {selected.map((tool) => (
            <AgentToolCard
              key={tool.id}
              context="network"
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

      <ImportToolsModal open={importOpen} onClose={() => setImportOpen(false)} projectId={projectId} importedToolIds={selectedIds} onImport={addTool} />
      <CreateToolModal open={createOpen} onClose={() => setCreateOpen(false)} projectId={projectId} agentId={agentId} onCreated={(tool) => { if (tool) addTool(tool); void refreshTools() }} />
      <EditToolModal tool={editingTool} onClose={() => setEditingTool(null)} onSaved={() => { setEditingTool(null); void refreshTools() }} />
    </div>
  )
}
