import { EmptyStatePanel, SectionBlock, TechnicalListItem } from '@woobe/ui'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { Shield, Wrench } from 'lucide-react'
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
  if (normalized === 'critical') return 'bg-red-300'
  if (normalized === 'high') return 'bg-orange-300'
  if (normalized === 'medium') return 'bg-amber-300'
  return 'bg-primary'
}

function RiskIndicator({ risk }: { risk?: string | null }) {
  const normalized = String(risk || 'unknown').toLowerCase()
  const activeDots = riskScore(risk)
  const dotTone = riskDotTone(risk)
  return (
    <span className="inline-flex h-[22px] items-center gap-1.5 rounded-technical border border-border bg-control/35 px-1.5 font-mono text-[8px] text-muted-foreground" title={`Risk: ${normalized}`} aria-label={`Risk: ${normalized}, ${activeDots} of 4`}>
      <Shield className="h-3 w-3 shrink-0" />
      <span className="flex items-center gap-0.5">{RISK_DOTS.map(index => <span key={index} className={`h-1.5 w-1.5 rounded-full ${index < activeDots ? dotTone : 'bg-muted/25'}`} />)}</span>
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
  const handleImport = (tool: Tool) => { onImport(tool); onClose() }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Import Tool"
      className="flex max-h-[min(720px,calc(100svh-2rem))] max-w-3xl flex-col overflow-hidden"
      contentClassName="min-h-0 p-0"
    >
      <div className="flex min-h-0 flex-col">
        <div className="border-b border-border px-4 py-3">
          <SectionBlock
            density="compact"
            eyebrow="Agent capability"
            title="Available Tools"
            description={`${availableTools.length} active Tool${availableTools.length === 1 ? '' : 's'} can be added to this Agent Draft.`}
            className="border-0 bg-transparent p-0"
          />
        </div>

        <div className="min-h-0 flex-1 p-4">
          {isLoading ? (
            <LoadingState variant="panel" layout="list" message="Loading tools..." />
          ) : availableTools.length === 0 ? (
            <EmptyStatePanel
              icon={<Wrench className="h-4 w-4" />}
              title="No active Tools available"
              description="Only active Tools that are not already bound to this Agent Draft are shown here."
            />
          ) : (
            <ScrollArea className="max-h-[430px] pr-1">
              <div className="space-y-1.5">
                {availableTools.map((tool) => (
                  <TechnicalListItem
                    key={tool.id}
                    label={tool.name}
                    description={tool.description || 'No description'}
                    leading={<span className="flex h-7 w-7 items-center justify-center rounded-control border border-border bg-control/35 text-primary-light"><Wrench className="h-3.5 w-3.5" /></span>}
                    meta={<><span>{tool.type}</span><RiskIndicator risk={tool.risk_level} /></>}
                    trailing={<Button size="sm" onClick={(event) => { event.stopPropagation(); handleImport(tool) }}>Import</Button>}
                    onClick={() => handleImport(tool)}
                  />
                ))}
              </div>
            </ScrollArea>
          )}
        </div>

        <div className="flex min-h-[52px] shrink-0 items-center justify-between border-t border-border bg-surface/[0.98] px-4 py-2.5">
          <p className="font-sans text-[8px] text-muted-foreground">Importing adds the Tool to the current Draft only.</p>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
        </div>
      </div>
    </Dialog>
  )
}
