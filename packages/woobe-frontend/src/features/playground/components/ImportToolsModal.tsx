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
  if (normalized === 'critical') return 'bg-red-300'
  if (normalized === 'high') return 'bg-orange-300'
  if (normalized === 'medium') return 'bg-amber-300'
  return 'bg-primary'
}

function RiskIndicator({ risk }: { risk?: string | null }) {
  const normalized = String(risk || 'unknown').toLowerCase()
  const activeDots = riskScore(risk)
  const dotTone = riskDotTone(risk)
  return <span className="inline-flex h-6 max-w-full items-center gap-1.5 rounded-technical border border-border bg-control/45 px-2 font-mono text-[8px] text-muted-foreground" title={`Risk: ${normalized}`} aria-label={`Risk: ${normalized}, ${activeDots} of 4`}><Shield className="h-3 w-3 shrink-0" /><span className="flex min-w-0 items-center gap-0.5">{RISK_DOTS.map(index => <span key={index} className={`h-1.5 w-1.5 shrink-0 rounded-full ${index < activeDots ? dotTone : 'bg-muted/25'}`} />)}</span></span>
}

interface ImportToolsModalProps { open: boolean; onClose: () => void; projectId: string; importedToolIds: Set<string>; onImport: (tool: Tool) => void }

export function ImportToolsModal({ open, onClose, projectId, importedToolIds, onImport }: ImportToolsModalProps) {
  const { data: allTools = [], isLoading } = useTools(projectId)
  const availableTools = allTools.filter(tool => tool.status === 'active' && !importedToolIds.has(tool.id))
  const handleImport = (tool: Tool) => { onImport(tool); onClose() }

  return <Dialog open={open} onClose={onClose} title="Import Tool" className="flex h-[min(680px,calc(100svh-2rem))] max-w-4xl flex-col overflow-hidden" contentClassName="min-h-0 flex-1 p-0">
    <div className="grid h-full min-h-0 grid-cols-[220px_minmax(0,1fr)] overflow-hidden">
      <aside className="border-r border-border bg-background/25 p-4"><span className="flex h-8 w-8 items-center justify-center rounded-control border border-border bg-control text-primary-light"><Wrench className="h-3.5 w-3.5" /></span><h3 className="mt-3 font-mono text-[9px] font-bold text-slate-50">Available tools</h3><p className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">{availableTools.length} active Tools can be added to this Draft.</p></aside>
      <section className="flex min-h-0 flex-col">
        <div className="min-h-0 flex-1 p-4">{isLoading ? <LoadingState variant="panel" layout="list" message="Loading tools..." /> : availableTools.length === 0 ? <div className="py-6"><EmptyState icon={<Wrench className="h-8 w-8" />} title="No active tools available" description="Only active Tools can be added to a new Agent Draft binding." /></div> : <ScrollArea className="h-full pr-1"><div className="divide-y divide-border/60 rounded-container border border-border bg-background/20">{availableTools.map((tool) => <div key={tool.id} className="grid gap-3 px-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><div className="min-w-0"><div className="flex items-center gap-2"><p className="truncate font-mono text-[9px] font-semibold text-slate-100">{tool.name}</p><RiskIndicator risk={tool.risk_level} /></div><p className="mt-1 line-clamp-2 font-sans text-[9px] leading-4 text-muted-foreground">{tool.description || 'No description'}</p><p className="mt-1.5 font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">{tool.type}</p></div><Button size="sm" onClick={() => handleImport(tool)}>Import</Button></div>)}</div></ScrollArea>}</div>
        <div className="flex min-h-[56px] shrink-0 justify-end gap-2 border-t border-border bg-surface/[0.98] px-4 py-3"><Button variant="outline" onClick={onClose}>Cancel</Button></div>
      </section>
    </div>
  </Dialog>
}
