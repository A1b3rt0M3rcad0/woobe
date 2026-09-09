import { useState } from 'react'
import { Link2, Plus, Wrench } from 'lucide-react'
import { toast } from 'sonner'

import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { Button } from '@/components/ui/Button'
import { AgentToolCard } from '@/features/tools/components/AgentToolCard'
import { isHttpToolGroup } from '@/features/tools/httpToolContract'
import { useTools } from '@/features/tools/hooks'
import type { HttpToolConfig, McpToolPermission, Tool } from '@/features/tools/types'
import { toolPermissionsFromTools, useAgentEditor } from '../AgentEditorContext'
import { CreateToolModal } from './CreateToolModal'
import { EditToolModal } from './EditToolModal'
import { ImportToolsModal } from './ImportToolsModal'

interface ToolsTabProps {
  projectId: string
  agentId: string
}

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

export function ToolsTab({ projectId, agentId }: ToolsTabProps) {
  const { data: allTools = [], isLoading, refetch } = useTools(projectId)
  const { state, setField, setState } = useAgentEditor()
  const [showImportModal, setShowImportModal] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingTool, setEditingTool] = useState<Tool | null>(null)

  const selectedIds = new Set(state.toolIds)
  const toolsById = new Map(allTools.map((tool) => [tool.id, tool]))
  const tools = state.toolIds.map((toolId) => toolsById.get(toolId)).filter((tool): tool is Tool => Boolean(tool))
  const activeCount = tools.filter((tool) => tool.status === 'active').length

  const refreshTools = async () => { await refetch() }

  const removeTool = (tool: Tool) => {
    const permissions = { ...state.toolPermissions }
    delete permissions[tool.id]
    setState({ ...state, toolIds: state.toolIds.filter((toolId) => toolId !== tool.id), toolPermissions: permissions })
    toast.success(`"${tool.name}" removed from draft`)
  }

  const addTool = (tool: Tool) => {
    if (selectedIds.has(tool.id)) return
    const initialPermissions = initialPermissionsForTool(tool)
    setState({
      ...state,
      toolIds: [...state.toolIds, tool.id],
      toolPermissions: { ...state.toolPermissions, [tool.id]: initialPermissions },
    })
    toast.success(`"${tool.name}" added to draft`)
  }

  const updatePermissions = (toolId: string, permissions: Record<string, McpToolPermission>) => {
    setField('toolPermissions', { ...state.toolPermissions, [toolId]: permissions })
  }

  if (isLoading) return <LoadingState variant="panel" layout="list" message="Loading tools..." />

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted">Tools</p>
          {tools.length > 0 ? <p className="mt-0.5 text-[10px] text-muted">{activeCount} of {tools.length} Project Tools active</p> : null}
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setShowCreateModal(true)}><Plus className="mr-1 h-4 w-4" />Create</Button>
          <Button size="sm" variant="outline" onClick={() => setShowImportModal(true)}><Link2 className="mr-1 h-4 w-4" />Import</Button>
        </div>
      </div>

      {tools.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface p-6">
          <EmptyState icon={<Wrench className="h-10 w-10" />} title="No tools selected" description="Create or import Project Tools to bind them to this Agent draft. Save Draft persists only the Agent binding and permission overrides." />
        </div>
      ) : (
        <div className="space-y-3">
          {tools.map((tool) => (
            <AgentToolCard
              key={tool.id}
              context="playground"
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

      <ImportToolsModal open={showImportModal} onClose={() => setShowImportModal(false)} projectId={projectId} importedToolIds={selectedIds} onImport={addTool} />
      <CreateToolModal open={showCreateModal} onClose={() => setShowCreateModal(false)} projectId={projectId} agentId={agentId} onCreated={(tool) => { if (tool) addTool(tool); void refreshTools() }} />
      <EditToolModal
        tool={editingTool}
        onClose={() => setEditingTool(null)}
        onSaved={() => {
          const savedTool = editingTool
          setEditingTool(null)
          const savedConfig = (savedTool?.config || {}) as HttpToolConfig
          if (savedTool && savedTool.type !== 'mcp' && !isHttpToolGroup(savedConfig)) {
            const permissions = { ...state.toolPermissions }
            delete permissions[savedTool.id]
            setField('toolPermissions', permissions)
          }
          if (savedTool && savedTool.type !== 'mcp') {
            toast.info('Project HTTP Tool updated. Save Draft to refresh this Agent snapshot.')
          }
          void refreshTools()
        }}
      />
    </div>
  )
}
