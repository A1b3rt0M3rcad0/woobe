import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/common/EmptyState'
import { Wrench, Plus, Link2, AlertTriangle } from 'lucide-react'
import { ImportToolsModal } from './ImportToolsModal'
import { CreateToolModal } from './CreateToolModal'

interface ToolsTabProps {
  projectId: string
  agentId: string
}

// TODO: Replace mock data with useAgentTools(agentId) from @/features/tools/hooks
interface MockTool {
  id: string
  name: string
  description: string
  type: string
  risk_level: string
}

const MOCK_TOOLS: MockTool[] = [
  { id: 'web-search', name: 'Web Search', description: 'Search the web for real-time information', type: 'builtin', risk_level: 'low' },
  { id: 'calculator', name: 'Calculator', description: 'Perform mathematical calculations and conversions', type: 'builtin', risk_level: 'none' },
  { id: 'code-executor', name: 'Code Executor', description: 'Execute Python code in a sandboxed environment', type: 'builtin', risk_level: 'medium' },
  { id: 'database-query', name: 'Database Query', description: 'Execute read-only SQL queries against connected databases', type: 'custom', risk_level: 'high' },
  { id: 'http-request', name: 'HTTP Request', description: 'Make HTTP requests to external APIs and services', type: 'builtin', risk_level: 'medium' },
  { id: 'file-reader', name: 'File Reader', description: 'Read and parse files from allowed directories', type: 'custom', risk_level: 'medium' },
]

const riskVariant: Record<string, 'default' | 'secondary' | 'success' | 'warning' | 'destructive'> = {
  none: 'default',
  low: 'success',
  medium: 'warning',
  high: 'destructive',
}

export function ToolsTab({ projectId, agentId }: ToolsTabProps) {
  const [showImportModal, setShowImportModal] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [importedTools, setImportedTools] = useState<Set<string>>(new Set())
  const [activeTools, setActiveTools] = useState<Set<string>>(new Set())
  const [customTools, setCustomTools] = useState<MockTool[]>([])

  const handleImport = (toolId: string) => {
    setImportedTools(prev => new Set(prev).add(toolId))
    setActiveTools(prev => new Set(prev).add(toolId))
  }

  const handleCreated = (tool: MockTool) => {
    setCustomTools(prev => [...prev, tool])
    setActiveTools(prev => new Set(prev).add(tool.id))
  }

  const handleRemove = (toolId: string) => {
    setImportedTools(prev => {
      const next = new Set(prev)
      next.delete(toolId)
      return next
    })
    setCustomTools(prev => prev.filter(t => t.id !== toolId))
    setActiveTools(prev => {
      const next = new Set(prev)
      next.delete(toolId)
      return next
    })
  }

  const toggleActive = (toolId: string) => {
    setActiveTools(prev => {
      const next = new Set(prev)
      if (next.has(toolId)) {
        next.delete(toolId)
      } else {
        next.add(toolId)
      }
      return next
    })
  }

  const agentTools = [
    ...customTools,
    ...MOCK_TOOLS.filter(t => importedTools.has(t.id)),
  ]
  const toolsToImport = MOCK_TOOLS.filter(t => !importedTools.has(t.id))

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
        {toolsToImport.length > 0 && (
          <Button size="sm" variant="outline" onClick={() => setShowImportModal(true)}>
            <Link2 className="mr-1 h-4 w-4" />
            Import
          </Button>
        )}
      </div>

      {agentTools.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface p-6">
          <EmptyState
            icon={<Wrench className="h-10 w-10" />}
            title="No tools imported"
            description="Import tools to give your agent additional capabilities."
            action={
              <div className="flex gap-2 mt-2">
                <Button size="sm" onClick={() => setShowCreateModal(true)}>
                  <Plus className="mr-1 h-4 w-4" />
                  Create Tool
                </Button>
                {toolsToImport.length > 0 && (
                  <Button size="sm" variant="outline" onClick={() => setShowImportModal(true)}>
                    <Link2 className="mr-1 h-4 w-4" />
                    Import Tools
                  </Button>
                )}
              </div>
            }
          />
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-muted uppercase tracking-wider">Agent Tools</p>
            <span className="text-[10px] text-muted">{activeTools.size} of {agentTools.length} active</span>
          </div>
          <div className="space-y-2">
            {agentTools.map((tool) => (
              <div key={tool.id} className="rounded-lg border border-border bg-background p-3 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate">{tool.name}</p>
                    <p className="text-xs text-muted mt-0.5">{tool.description}</p>
                  </div>
                  <Badge variant={riskVariant[tool.risk_level] || 'default'}>{tool.risk_level}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-muted uppercase tracking-wider">{tool.type}</span>
                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant={activeTools.has(tool.id) ? 'default' : 'outline'}
                      onClick={() => toggleActive(tool.id)}
                    >
                      {activeTools.has(tool.id) ? 'Active' : 'Activate'}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-400 hover:text-red-300"
                      onClick={() => handleRemove(tool.id)}
                    >
                      Remove
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <ImportToolsModal
        open={showImportModal}
        onClose={() => setShowImportModal(false)}
        importedToolIds={Array.from(importedTools)}
        onImport={handleImport}
      />

      <CreateToolModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        projectId={projectId}
        agentId={agentId}
        onCreated={handleCreated}
      />
    </div>
  )
}
