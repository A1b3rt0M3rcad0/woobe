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
  standalone?: boolean
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

export function ToolsTab({ projectId, agentId, standalone = false }: ToolsTabProps) {
  const { data: allTools = [], isLoading, refetch } = useTools(projectId)
  const { state, setField, setState } = useAgentEditor()
  const [showImportModal, setShowImportModal] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingTool, setEditingTool] = useState<Tool | null>(null)

  const toolIds = state.toolIds ?? []
  const toolPermissions = state.toolPermissions ?? {}
  const selectedIds = new Set(toolIds)
  const toolsById = new Map(allTools.map((tool) => [tool.id, tool]))
  const tools = toolIds.map((toolId) => toolsById.get(toolId)).filter((tool): tool is Tool => Boolean(tool))
  const activeCount = tools.filter((tool) => tool.status === 'active').length

  const refreshTools = async () => { await refetch() }

  const removeTool = (tool: Tool) => {
    const permissions = { ...toolPermissions }
    delete permissions[tool.id]
    setState({ ...state, toolIds: toolIds.filter((toolId) => toolId !== tool.id), toolPermissions: permissions })
    toast.success(`"${tool.name}" removed from draft`)
  }

  const addTool = (tool: Tool) => {
    if (selectedIds.has(tool.id)) return
    const initialPermissions = initialPermissionsForTool(tool)
    setState({
      ...state,
      toolIds: [...toolIds, tool.id],
      toolPermissions: { ...toolPermissions, [tool.id]: initialPermissions },
    })
    toast.success(`"${tool.name}" added to draft`)
  }

  const updatePermissions = (toolId: string, permissions: Record<string, McpToolPermission>) => {
    setField('toolPermissions', { ...toolPermissions, [toolId]: permissions })
  }

  if (isLoading) return <LoadingState variant="panel" layout="list" message="Loading tools..." />

  const actions = (
    <div className="flex gap-2">
      <Button size="sm" variant="outline" onClick={() => setShowCreateModal(true)}><Plus className="mr-1 h-4 w-4" />Create</Button>
      <Button size="sm" variant="outline" onClick={() => setShowImportModal(true)}><Link2 className="mr-1 h-4 w-4" />Import</Button>
    </div>
  )

  const toolList = tools.length === 0 ? (
    <div className={standalone ? 'rounded-lg border border-dashed border-border bg-background/35 p-5' : 'rounded-xl border border-border bg-surface p-6'}>
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
          permissionOverrides={toolPermissions[tool.id] || {}}
          onPermissionOverridesChange={(permissions) => updatePermissions(tool.id, permissions)}
        />
      ))}
    </div>
  )

  return (
    <>
      {standalone ? (
        <section aria-label="Tools" className="space-y-4 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-white">Tools</p>
              <p className="mt-1 text-[11px] leading-4 text-muted">
                Bind reusable Project Tools to this Agent. Project status remains read-only from the Agent inspector.
              </p>
              {tools.length > 0 ? <p className="mt-1 text-[10px] text-muted">{activeCount} of {tools.length} Project Tools active</p> : null}
            </div>
            {actions}
          </div>
          {toolList}
        </section>
      ) : (
        <div className="space-y-3 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-muted">Tools</p>
              {tools.length > 0 ? <p className="mt-0.5 text-[10px] text-muted">{activeCount} of {tools.length} Project Tools active</p> : null}
            </div>
            {actions}
          </div>
          {toolList}
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
            const permissions = { ...toolPermissions }
            delete permissions[savedTool.id]
            setField('toolPermissions', permissions)
          }
          if (savedTool && savedTool.type !== 'mcp') {
            toast.info('Project HTTP Tool updated. Save Draft to refresh this Agent snapshot.')
          }
          void refreshTools()
        }}
      />
    </>
  )
}
