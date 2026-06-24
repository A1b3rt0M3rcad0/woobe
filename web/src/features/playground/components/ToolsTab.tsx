import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { Wrench, Plus, Link2, AlertTriangle, Circle, XCircle, Pencil } from 'lucide-react'
import { ImportToolsModal } from './ImportToolsModal'
import { CreateToolModal } from './CreateToolModal'
import { EditToolModal } from './EditToolModal'
import { McpProviderPanel, isMcpProviderTool } from '@/features/tools/components/McpProviderPanel'
import { useAgentTools, useUpdateToolStatus, useUpdateTool, useTools } from '@/features/tools/hooks'
import type { Tool } from '@/features/tools/types'
import { toast } from 'sonner'

interface ToolsTabProps {
  projectId: string
  agentId: string
}

const riskVariant: Record<string, 'default' | 'secondary' | 'success' | 'warning' | 'destructive'> = {
  low: 'success',
  medium: 'warning',
  high: 'destructive',
  critical: 'destructive',
}

export function ToolsTab({ projectId, agentId }: ToolsTabProps) {
  const { data: tools = [], isLoading, refetch } = useAgentTools(agentId)
  const { refetch: refetchProjectTools } = useTools(projectId)
  const updateStatus = useUpdateToolStatus()
  const updateTool = useUpdateTool()

  const [showImportModal, setShowImportModal] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingTool, setEditingTool] = useState<Tool | null>(null)

  const agentToolIds = new Set(tools.map(t => t.id))

  const refetchAll = async () => {
    await Promise.all([refetch(), refetchProjectTools()])
  }

  const handleToggleActive = async (tool: Tool) => {
    try {
      const newStatus = tool.status === 'active' ? 'inactive' : 'active'
      await updateStatus.mutateAsync({ toolId: tool.id, data: { status: newStatus } })
      toast.success(`"${tool.name}" ${newStatus === 'active' ? 'activated' : 'deactivated'}`)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update status')
    }
  }

  const handleRemove = async (tool: Tool) => {
    try {
      await updateTool.mutateAsync({ toolId: tool.id, data: { agent_id: null } })
      toast.success(`"${tool.name}" removed from agent`)
      refetch()
      refetchProjectTools()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove tool from agent')
    }
  }

  const handleCreated = (_tool?: Tool) => {
    refetch()
    refetchProjectTools()
  }

  const handleImport = () => {
    refetch()
    refetchProjectTools()
  }

  const handleEdit = (tool: Tool) => {
    setEditingTool(tool)
  }

  const handleEditSaved = () => {
    setEditingTool(null)
    refetch()
    refetchProjectTools()
  }

  if (isLoading) return <LoadingState />

  return (
    <div className="p-4 space-y-4">
      <div className="rounded-lg border border-blue-500/30 bg-blue-500/5 p-3">
        <div className="flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 text-blue-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-medium text-blue-300">Grant capabilities to the agent</p>
            <p className="text-xs text-muted mt-1">
              Activate tools to let the agent interact with external systems, execute code, and access real-time data during runs.
            </p>
          </div>
        </div>
      </div>

      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={() => setShowCreateModal(true)}>
          <Plus className="mr-1 h-4 w-4" />
          Create
        </Button>
        <Button size="sm" variant="outline" onClick={() => setShowImportModal(true)}>
          <Link2 className="mr-1 h-4 w-4" />
          Import
        </Button>
      </div>

      {tools.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface p-6">
          <EmptyState
            icon={<Wrench className="h-10 w-10" />}
            title="No tools imported"
            description="Create or import tools to give your agent additional capabilities."
            action={
              <div className="flex gap-2 mt-2">
                <Button size="sm" onClick={() => setShowCreateModal(true)}>
                  <Plus className="mr-1 h-4 w-4" />
                  Create Tool
                </Button>
                <Button size="sm" variant="outline" onClick={() => setShowImportModal(true)}>
                  <Link2 className="mr-1 h-4 w-4" />
                  Import Tools
                </Button>
              </div>
            }
          />
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-muted uppercase tracking-wider">Agent Tools</p>
            <span className="text-[10px] text-muted">{tools.filter(t => t.status === 'active').length} of {tools.length} active</span>
          </div>
          <div className="space-y-2">
            {tools.map((tool) => {
              const isActive = tool.status === 'active'
              const isMcp = isMcpProviderTool(tool)
              return (
              <div key={tool.id} className={`rounded-lg border p-3 space-y-2 transition-opacity ${isActive ? 'border-border bg-background' : 'border-border/50 bg-background/50 opacity-70'}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      {isActive ? (
                        <Circle className="h-2.5 w-2.5 fill-emerald-400 text-emerald-400 shrink-0" />
                      ) : (
                        <XCircle className="h-2.5 w-2.5 text-muted shrink-0" />
                      )}
                      <p className="text-sm font-medium truncate">{tool.name}</p>
                      <Badge variant={isActive ? 'success' : 'secondary'} className="text-[10px] px-1 py-0">
                        {isActive ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted mt-0.5">{tool.description || 'No description'}</p>
                  </div>
                  <Badge variant={riskVariant[tool.risk_level] || 'default'}>{tool.risk_level}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-muted uppercase tracking-wider">{tool.type}</span>
                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant={isActive ? 'default' : 'outline'}
                      onClick={() => handleToggleActive(tool)}
                    >
                      {isActive ? 'Active' : 'Activate'}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleEdit(tool)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-400 hover:text-red-300"
                      onClick={() => handleRemove(tool)}
                    >
                      Remove
                    </Button>
                  </div>
                </div>
                {isMcp ? <McpProviderPanel tool={tool} onChanged={refetchAll} /> : null}
              </div>
              )
            })}
          </div>
        </>
      )}

      <ImportToolsModal
        open={showImportModal}
        onClose={() => setShowImportModal(false)}
        projectId={projectId}
        agentId={agentId}
        importedToolIds={agentToolIds}
        onImport={handleImport}
      />

      <CreateToolModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        projectId={projectId}
        agentId={agentId}
        onCreated={handleCreated}
      />

      <EditToolModal
        tool={editingTool}
        onClose={() => setEditingTool(null)}
        onSaved={handleEditSaved}
      />
    </div>
  )
}
