import { useState, type ReactNode } from 'react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { Wrench, Plus, Link2, Pencil, Shield, Trash2 } from 'lucide-react'
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

function toolTypeLabel(tool: Tool): string {
  const config = (tool.config || {}) as Record<string, unknown>
  if (String(tool.type).toLowerCase() === 'mcp' || config.protocol === 'mcp') return 'MCP'
  if (String(tool.type).toLowerCase().includes('http')) return 'HTTP'
  return String(tool.type || 'Tool').replace(/_/g, ' ').toUpperCase()
}

function ToolTypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex h-8 items-center rounded-xl bg-muted/15 px-3 text-xs font-semibold uppercase tracking-wide text-white ring-1 ring-border/70">
      {type}
    </span>
  )
}

function RiskIndicator({ risk }: { risk?: string | null }) {
  const normalized = String(risk || 'unknown').toLowerCase()
  const activeDots =
    normalized === 'critical' || normalized === 'high'
      ? 3
      : normalized === 'medium'
        ? 2
        : normalized === 'low'
          ? 1
          : 0

  const dotTone =
    normalized === 'critical' || normalized === 'high'
      ? 'bg-red-300 shadow-red-400/20'
      : normalized === 'medium'
        ? 'bg-amber-300 shadow-amber-400/20'
        : 'bg-primary shadow-primary/20'

  return (
    <span
      className="inline-flex h-8 items-center gap-2 rounded-xl border border-border/80 bg-background/70 px-2.5 text-muted"
      title={`Risk: ${normalized}`}
      aria-label={`Risk: ${normalized}`}
    >
      <Shield className="h-4 w-4 text-white/90" />
      <span className="flex items-center gap-1">
        {[0, 1, 2].map(index => (
          <span
            key={index}
            className={`h-2 w-2 rounded-full ${index < activeDots ? `${dotTone} shadow-sm` : 'bg-muted/25'}`}
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
      className={`relative h-9 w-16 shrink-0 rounded-full border transition-all focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50 ${
        active
          ? 'border-primary/45 bg-primary/10 shadow-sm shadow-primary/10'
          : 'border-border bg-background/80'
      }`}
    >
      <span
        className={`absolute top-1/2 h-7 w-7 -translate-y-1/2 rounded-full transition-all ${
          active
            ? 'left-8 bg-primary shadow-lg shadow-primary/20'
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
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border bg-background/50 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50 ${
        tone === 'danger'
          ? 'border-red-500/25 text-red-200 hover:bg-red-500/10 hover:text-red-100'
          : 'border-border/80 text-white/80 hover:bg-accent hover:text-white'
      }`}
    >
      {children}
    </button>
  )
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
  const activeCount = tools.filter(tool => tool.status === 'active').length

  const refetchAll = async () => {
    await Promise.all([refetch(), refetchProjectTools()])
  }

  const handleToggleActive = async (tool: Tool) => {
    try {
      const newStatus = tool.status === 'active' ? 'inactive' : 'active'
      await updateStatus.mutateAsync({ toolId: tool.id, data: { status: newStatus } })
      toast.success(`"${tool.name}" ${newStatus === 'active' ? 'activated' : 'deactivated'}`)
      await refetchAll()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update status')
    }
  }

  const handleRemove = async (tool: Tool) => {
    try {
      await updateTool.mutateAsync({ toolId: tool.id, data: { agent_id: null } })
      toast.success(`"${tool.name}" removed from agent`)
      await refetchAll()
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

  const handleEditSaved = () => {
    setEditingTool(null)
    refetch()
    refetchProjectTools()
  }

  if (isLoading) return <LoadingState />

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted">Agent tools</p>
          <p className="mt-0.5 text-[10px] text-muted">{activeCount} of {tools.length} active</p>
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
            title="No tools imported"
            description="Create or import tools to give this agent extra capabilities."
            action={
              <div className="mt-2 flex gap-2">
                <Button size="sm" onClick={() => setShowCreateModal(true)}>
                  <Plus className="mr-1 h-4 w-4" />
                  Create
                </Button>
                <Button size="sm" variant="outline" onClick={() => setShowImportModal(true)}>
                  <Link2 className="mr-1 h-4 w-4" />
                  Import
                </Button>
              </div>
            }
          />
        </div>
      ) : (
        <div className="space-y-4">
          {tools.map((tool) => {
            const isActive = tool.status === 'active'
            const isMcp = isMcpProviderTool(tool)
            return (
              <article
                key={tool.id}
                className={`rounded-2xl border p-5 shadow-sm transition-all ${
                  isActive
                    ? 'border-border bg-background'
                    : 'border-border/50 bg-background/50 opacity-70'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1 space-y-1">
                    <h3 className="truncate text-xl font-semibold tracking-tight text-white">
                      {tool.name}
                    </h3>
                    <p className="line-clamp-2 text-sm leading-relaxed text-muted">
                      {tool.description || 'No description'}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <ToolStatusToggle
                      active={isActive}
                      loading={updateStatus.isPending}
                      onClick={() => handleToggleActive(tool)}
                    />
                    <ToolIconButton label="Edit tool" onClick={() => setEditingTool(tool)}>
                      <Pencil className="h-4 w-4" />
                    </ToolIconButton>
                    <ToolIconButton
                      label="Remove tool from agent"
                      tone="danger"
                      loading={updateTool.isPending}
                      onClick={() => handleRemove(tool)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </ToolIconButton>
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-2">
                  <ToolTypeBadge type={toolTypeLabel(tool)} />
                  <RiskIndicator risk={tool.risk_level} />
                </div>

                {isMcp ? <div className="mt-5"><McpProviderPanel tool={tool} onChanged={refetchAll} /></div> : null}
              </article>
            )
          })}
        </div>
      )}

      <ImportToolsModal open={showImportModal} onClose={() => setShowImportModal(false)} projectId={projectId} agentId={agentId} importedToolIds={agentToolIds} onImport={handleImport} />
      <CreateToolModal open={showCreateModal} onClose={() => setShowCreateModal(false)} projectId={projectId} agentId={agentId} onCreated={handleCreated} />
      <EditToolModal tool={editingTool} onClose={() => setEditingTool(null)} onSaved={handleEditSaved} />
    </div>
  )
}
