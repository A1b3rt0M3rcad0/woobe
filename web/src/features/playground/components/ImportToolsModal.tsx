import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { Wrench } from 'lucide-react'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { useTools, useUpdateTool } from '@/features/tools/hooks'
import type { Tool } from '@/features/tools/types'
import { toast } from 'sonner'

const riskVariant: Record<string, 'default' | 'secondary' | 'success' | 'warning' | 'destructive'> = {
  low: 'success',
  medium: 'warning',
  high: 'destructive',
  critical: 'destructive',
}

interface ImportToolsModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  importedToolIds: Set<string>
  onImport: () => void
}

export function ImportToolsModal({ open, onClose, projectId, agentId, importedToolIds, onImport }: ImportToolsModalProps) {
  const { data: allTools = [], isLoading } = useTools(projectId)
  const updateTool = useUpdateTool()

  const availableTools = allTools.filter(t => !importedToolIds.has(t.id))

  const handleImport = async (tool: Tool) => {
    try {
      await updateTool.mutateAsync({
        toolId: tool.id,
        data: { agent_id: agentId },
      })
      toast.success(`"${tool.name}" imported`)
      onImport()
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to import tool')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Import Tool">
      <div className="space-y-4">
        {isLoading ? (
          <LoadingState />
        ) : availableTools.length === 0 ? (
          <div className="py-6">
            <EmptyState
              icon={<Wrench className="h-10 w-10" />}
              title="All tools imported"
              description="All available tools have already been added to this agent."
            />
          </div>
        ) : (
          <ScrollArea className="max-h-[400px] pr-1">
            <div className="space-y-2">
              {availableTools.map((tool) => (
                <div key={tool.id} className="rounded-lg border border-border bg-background p-3 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{tool.name}</p>
                      <p className="text-xs text-muted mt-0.5">{tool.description || 'No description'}</p>
                    </div>
                    <Badge variant={riskVariant[tool.risk_level] || 'default'}>{tool.risk_level}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted uppercase tracking-wider">{tool.type}</span>
                    <Button
                      size="sm"
                      onClick={() => handleImport(tool)}
                      loading={updateTool.isPending}
                    >
                      Import
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
