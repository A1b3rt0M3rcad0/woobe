import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { Wrench } from 'lucide-react'
import { EmptyState } from '@/components/common/EmptyState'

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

interface ImportToolsModalProps {
  open: boolean
  onClose: () => void
  importedToolIds: string[]
  onImport: (toolId: string) => void
}

export function ImportToolsModal({ open, onClose, importedToolIds, onImport }: ImportToolsModalProps) {
  const availableTools = MOCK_TOOLS.filter(t => !importedToolIds.includes(t.id))

  return (
    <Dialog open={open} onClose={onClose} title="Import Tool">
      <div className="space-y-4">
        {availableTools.length === 0 ? (
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
                      <p className="text-xs text-muted mt-0.5">{tool.description}</p>
                    </div>
                    <Badge variant={riskVariant[tool.risk_level] || 'default'}>{tool.risk_level}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted uppercase tracking-wider">{tool.type}</span>
                    <Button
                      size="sm"
                      onClick={() => {
                        onImport(tool.id)
                        onClose()
                      }}
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
