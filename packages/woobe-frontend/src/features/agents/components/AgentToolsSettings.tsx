import { useState } from 'react'
import { Link2, Wrench } from 'lucide-react'
import { toast } from 'sonner'
import { EmptyStatePanel, PanelHeader } from '@woobe/ui'

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
    setState({ ...state, toolIds: [...state.toolIds, tool.id], toolPermissions: { ...state.toolPermissions, [tool.id]: initialPermissions } })
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
    <div className="p-ui-md">
      <section aria-label="Tools" className="rounded-container border border-border bg-surface/[0.72]">
        <PanelHeader icon={<Wrench className="h-3.5 w-3.5" />} title="Tools" description={`${selected.length} bound to this Draft`} />
        <div className="p-ui-md">
          <p className="font-sans text-product-caption text-muted-foreground">Control which Tools this Agent can use.</p>
          <div className="mt-ui-md grid grid-cols-2 gap-ui-sm">
            <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}><Link2 className="h-3.5 w-3.5" />Import</Button>
            <Button size="sm" variant="ghost" className="text-primary-light" onClick={() => setCreateOpen(true)}>Create</Button>
          </div>
          <p className="mb-ui-sm mt-ui-lg font-mono text-system-meta font-semibold uppercase tracking-[0.1em] text-muted-foreground">Bound tools</p>
          {toolsQuery.isLoading ? (
            <p role="status" className="font-mono text-system-meta text-muted-foreground">Loading Tools...</p>
          ) : selected.length === 0 ? (
            <EmptyStatePanel compact title="No Tools selected" description="Create or import Tools for this Agent Draft." />
          ) : (
            <div className="space-y-ui-sm">
              {selected.map((tool) => (
                <AgentToolCard key={tool.id} context="agent" tool={tool} onChanged={refreshTools} onEdit={() => setEditingTool(tool)} onRemove={() => removeTool(tool)} permissionOverrides={state.toolPermissions[tool.id] || {}} onPermissionOverridesChange={(permissions) => updatePermissions(tool.id, permissions)} />
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
