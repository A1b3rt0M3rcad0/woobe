import { useState, type ReactNode } from 'react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { Wrench, Plus, Link2, Pencil, Shield, Trash2 } from 'lucide-react'
import { ImportToolsModal } from './ImportToolsModal'
import { CreateToolModal } from './CreateToolModal'
import { EditToolModal } from './EditToolModal'
import { McpProviderPanel, isMcpProviderTool } from '@/features/tools/components/McpProviderPanel'
import { useUpdateToolStatus, useTools } from '@/features/tools/hooks'
import type { McpToolPermission, Tool } from '@/features/tools/types'
import { toolPermissionsFromTools, useAgentEditor } from '../AgentEditorContext'
import { toast } from 'sonner'

interface ToolsTabProps {
  projectId: string
  agentId: string
}

const RISK_DOTS = [0, 1, 2, 3]

function riskScore(risk?: string | null): number {
  const normalized = String(risk || '').toLowerCase()
  if (normalized === 'critical') return 4
  if (normalized === 'high') return 3
  if (normalized === 'medium') return 2
  if (normalized === 'low') return 1
  return 0
}

function riskDotTone(risk?: string | null): string {
  const normalized = String(risk || '').toLowerCase()
  if (normalized === 'critical') return 'bg-red-300 shadow-red-400/20'
  if (normalized === 'high') return 'bg-orange-300 shadow-orange-400/20'
  if (normalized === 'medium') return 'bg-amber-300 shadow-amber-400/20'
  return 'bg-primary shadow-primary/20'
}

function toolTypeLabel(tool: Tool): string {
  const config = (tool.config || {}) as Record<string, unknown>
  if (String(tool.type).toLowerCase() === 'mcp' || config.protocol === 'mcp') return 'MCP'
  if (String(tool.type).toLowerCase().includes('http')) return 'HTTP'
  return String(tool.type || 'Tool').replace(/_/g, ' ').toUpperCase()
}

function ToolTypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex h-6 items-center rounded-lg bg-muted/15 px-2 text-[10px] font-semibold uppercase tracking-wide text-white ring-1 ring-border/70">
      {type}
    </span>
  )
}

function RiskIndicator({ risk }: { risk?: string | null }) {
  const normalized = String(risk || 'unknown').toLowerCase()
  const activeDots = riskScore(risk)
  const dotTone = riskDotTone(risk)

  return (
    <span
      className="inline-flex h-6 max-w-full items-center gap-1.5 rounded-lg border border-border/80 bg-background/70 px-2 text-muted"
      title={`Risk: ${normalized}`}
      aria-label={`Risk: ${normalized}, ${activeDots} of 4`}
    >
      <Shield className="h-3.5 w-3.5 shrink-0 text-white/90" />
      <span className="flex min-w-0 items-center gap-0.5">
        {RISK_DOTS.map(index => (
          <span
            key={index}
            className={`h-1.5 w-1.5 shrink-0 rounded-full ${index < activeDots ? `${dotTone} shadow-sm` : 'bg-muted/25'}`}
          />
        ))}
      </span>
    </span>
  )
}

function ToolStatusToggle({
  active,
  loading,
  onClick,
}: {
  active: boolean
  loading?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      aria-label={active ? 'Turn tool off' : 'Turn tool on'}
      aria-pressed={active}
      disabled={loading}
      onClick={onClick}
      className={`relative h-6 w-9 shrink-0 rounded-full border transition-all focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50 ${
        active
          ? 'border-primary/45 bg-primary/10 shadow-sm shadow-primary/10'
          : 'border-border bg-background/80'
      }`}
    >
      <span
        className={`absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full transition-all ${
          active
            ? 'left-4 bg-primary shadow-sm shadow-primary/20'
            : 'left-1 bg-muted'
        }`}
      />
    </button>
  )
}

function ToolIconButton({
  label,
  tone = 'default',
  loading,
  onClick,
  children,
}: {
  label: string
  tone?: 'default' | 'danger'
  loading?: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={loading}
      onClick={onClick}
      className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border bg-background/50 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50 ${
        tone === 'danger'
          ? 'border-red-500/30 text-red-200 hover:bg-red-500/10 hover:text-red-100'
          : 'border-border/80 text-white/80 hover:bg-accent hover:text-white'
      }`}
    >
      {children}
    </button>
  )
}

export function ToolsTab({ projectId, agentId }: ToolsTabProps) {
  const { data: allTools = [], isLoading, refetch } = useTools(projectId)
  const updateStatus = useUpdateToolStatus()
  const { state, setField, setState } = useAgentEditor()

  const [showImportModal, setShowImportModal] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingTool, setEditingTool] = useState<Tool | null>(null)

  const selectedIds = new Set(state.toolIds)
  const toolsById = new Map(allTools.map((tool) => [tool.id, tool]))
  const tools = state.toolIds.map((toolId) => toolsById.get(toolId)).filter((tool): tool is Tool => Boolean(tool))
  const activeCount = tools.filter(tool => tool.status === 'active').length

  const refreshTools = async (): Promise<void> => {
    await refetch()
  }

  const handleToggleActive = async (tool: Tool) => {
    if (tool.status === 'deprecated') return
    try {
      const newStatus = tool.status === 'active' ? 'inactive' : 'active'
      await updateStatus.mutateAsync({ toolId: tool.id, data: { status: newStatus } })
      toast.success(`"${tool.name}" ${newStatus === 'active' ? 'activated' : 'deactivated'}`)
      await refreshTools()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update status')
    }
  }

  const handleRemove = (tool: Tool) => {
    const nextPermissions = { ...state.toolPermissions }
    delete nextPermissions[tool.id]
    setState({
      ...state,
      toolIds: state.toolIds.filter((toolId) => toolId !== tool.id),
      toolPermissions: nextPermissions,
    })
    toast.success(`"${tool.name}" removed from draft`)
  }

  const addToolToDraft = (tool: Tool) => {
    if (selectedIds.has(tool.id)) return
    const initialPermissions = toolPermissionsFromTools([tool])[tool.id] || {}
    setState({
      ...state,
      toolIds: [...state.toolIds, tool.id],
      toolPermissions: {
        ...state.toolPermissions,
        [tool.id]: initialPermissions,
      },
    })
    toast.success(`"${tool.name}" added to draft`)
  }

  const handlePermissionOverridesChange = (toolId: string, permissions: Record<string, McpToolPermission>) => {
    setField('toolPermissions', {
      ...state.toolPermissions,
      [toolId]: permissions,
    })
  }

  const handleCreated = (tool?: Tool) => {
    if (tool) addToolToDraft(tool)
    void refreshTools()
  }

  const handleEditSaved = () => {
    setEditingTool(null)
    void refreshTools()
  }

  if (isLoading) return <LoadingState variant="panel" layout="list" message="Loading tools..." />

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted">Tools</p>
          {tools.length > 0 && (
            <p className="mt-0.5 text-[10px] text-muted">{activeCount} of {tools.length} active</p>
          )}
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
      </div>

      {tools.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface p-6">
          <EmptyState
            icon={<Wrench className="h-10 w-10" />}
            title="No tools selected"
            description="Create or import tools to add them to this Agent draft. Save Draft persists the selection."
          />
        </div>
      ) : (
        <div className="space-y-3">
          {tools.map((tool) => {
            const isActive = tool.status === 'active'
            const isRetired = tool.status === 'deprecated'
            const isMcp = isMcpProviderTool(tool)
            return (
              <article
                key={tool.id}
                className={`rounded-xl border p-3 shadow-sm transition-all ${
                  isRetired
                    ? 'border-amber-500/30 bg-amber-500/5'
                    : isActive
                      ? 'border-border bg-background'
                      : 'border-border/50 bg-background/50 opacity-70'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1 space-y-0.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate text-sm font-semibold text-white">
                        {tool.name}
                      </h3>
                      {isRetired && (
                        <span className="rounded-full border border-amber-500/35 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-200">
                          Retired globally
                        </span>
                      )}
                    </div>
                    <p className="line-clamp-2 text-xs leading-relaxed text-muted">
                      {tool.description || 'No description'}
                    </p>
                    {isRetired && (
                      <p className="pt-1 text-[11px] leading-5 text-amber-200/80">
                        Existing Agent snapshots remain valid. This Tool cannot be added to new Agent bindings.
                      </p>
                    )}
                  </div>

                  <div className="flex shrink-0 items-center gap-1.5">
                    {!isRetired && (
                      <ToolStatusToggle
                        active={isActive}
                        loading={updateStatus.isPending}
                        onClick={() => handleToggleActive(tool)}
                      />
                    )}
                    {!isRetired && (
                      <ToolIconButton label="Edit tool" onClick={() => setEditingTool(tool)}>
                        <Pencil className="h-3.5 w-3.5" />
                      </ToolIconButton>
                    )}
                    <ToolIconButton
                      label="Remove tool from draft"
                      tone="danger"
                      onClick={() => handleRemove(tool)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </ToolIconButton>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <ToolTypeBadge type={toolTypeLabel(tool)} />
                  <RiskIndicator risk={tool.risk_level} />
                </div>

                {isMcp ? (
                  <div className="mt-3">
                    <McpProviderPanel
                      tool={tool}
                      onChanged={refreshTools}
                      permissionOverrides={state.toolPermissions[tool.id] || {}}
                      onPermissionOverridesChange={(permissions) => handlePermissionOverridesChange(tool.id, permissions)}
                    />
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>
      )}

      <ImportToolsModal open={showImportModal} onClose={() => setShowImportModal(false)} projectId={projectId} importedToolIds={selectedIds} onImport={addToolToDraft} />
      <CreateToolModal open={showCreateModal} onClose={() => setShowCreateModal(false)} projectId={projectId} agentId={agentId} onCreated={handleCreated} />
      <EditToolModal tool={editingTool} onClose={() => setEditingTool(null)} onSaved={handleEditSaved} />
    </div>
  )
}
