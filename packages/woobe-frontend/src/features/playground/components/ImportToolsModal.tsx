import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { Shield, Wrench } from 'lucide-react'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { useTools } from '@/features/tools/hooks'
import type { Tool } from '@/features/tools/types'

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

function RiskIndicator({ risk }: { risk?: string | null }) {
  const normalized = String(risk || 'unknown').toLowerCase()
  const activeDots = riskScore(risk)
  const dotTone = riskDotTone(risk)

  return (
    <span className="inline-flex h-6 max-w-full items-center gap-1.5 rounded-lg border border-border/80 bg-background/70 px-2 text-muted" title={`Risk: ${normalized}`} aria-label={`Risk: ${normalized}, ${activeDots} of 4`}>
      <Shield className="h-3.5 w-3.5 shrink-0 text-white/90" />
      <span className="flex min-w-0 items-center gap-0.5">
        {RISK_DOTS.map(index => (
          <span key={index} className={`h-1.5 w-1.5 shrink-0 rounded-full ${index < activeDots ? `${dotTone} shadow-sm` : 'bg-muted/25'}`} />
        ))}
      </span>
    </span>
  )
}

interface ImportToolsModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  importedToolIds: Set<string>
  onImport: (tool: Tool) => void
}

export function ImportToolsModal({ open, onClose, projectId, importedToolIds, onImport }: ImportToolsModalProps) {
  const { data: allTools = [], isLoading } = useTools(projectId)
  const availableTools = allTools.filter(tool => tool.status === 'active' && !importedToolIds.has(tool.id))

  const handleImport = (tool: Tool) => {
    onImport(tool)
    onClose()
  }

  return (
    <Dialog open={open} onClose={onClose} title="Import Tool" className="max-w-4xl overflow-hidden bg-surface/95">
      <div className="grid max-h-[70vh] grid-cols-[240px_1fr] gap-0 overflow-hidden -m-6">
        <aside className="border-r border-border/90 bg-background/25 p-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">
            <Wrench className="h-4 w-4" />
          </div>
          <h3 className="mt-4 text-sm font-semibold text-white">Available tools</h3>
          <p className="mt-1 text-xs text-muted">{availableTools.length} active tools can be added to this draft.</p>
        </aside>

        <section className="flex min-h-0 flex-col">
          <div className="min-h-0 flex-1 p-5">
            {isLoading ? (
              <LoadingState variant="panel" layout="list" message="Loading tools..." />
            ) : availableTools.length === 0 ? (
              <div className="py-6">
                <EmptyState icon={<Wrench className="h-10 w-10" />} title="No active tools available" description="Only active Tools can be added to a new Agent draft binding." />
              </div>
            ) : (
              <ScrollArea className="max-h-[480px] pr-1">
                <div className="space-y-2">
                  {availableTools.map((tool) => (
                    <div key={tool.id} className="space-y-2 rounded-xl border border-border/80 bg-background/45 p-3 shadow-sm shadow-black/5">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-white">{tool.name}</p>
                          <p className="mt-0.5 text-xs text-muted">{tool.description || 'No description'}</p>
                        </div>
                        <RiskIndicator risk={tool.risk_level} />
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] uppercase tracking-wider text-muted">{tool.type}</span>
                        <Button size="sm" onClick={() => handleImport(tool)}>Import</Button>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </div>
          <div className="flex justify-end gap-2 border-t border-border/90 bg-background/20 p-4"><Button variant="outline" onClick={onClose}>Cancel</Button></div>
        </section>
      </div>
    </Dialog>
  )
}
