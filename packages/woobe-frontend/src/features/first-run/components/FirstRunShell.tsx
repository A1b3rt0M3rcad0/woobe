import type { ReactNode } from 'react'
import { ArrowLeft, Check } from 'lucide-react'
import { SectionBlock } from '@woobe/ui'
import { Button } from '@/components/ui/Button'

export type FirstRunStage = 'project' | 'agent' | 'test'

interface FirstRunShellProps {
  workspaceName: string
  projectName?: string
  activeStage: FirstRunStage
  onExit: () => void
  children: ReactNode
}

const stages: Array<{ key: FirstRunStage; label: string; description: string }> = [
  { key: 'project', label: 'Project', description: 'Create the technical boundary.' },
  { key: 'agent', label: 'Agent', description: 'Configure the first operational Agent.' },
  { key: 'test', label: 'First test', description: 'Run the Agent in the Playground.' },
]

export function FirstRunShell({ workspaceName, projectName, activeStage, onExit, children }: FirstRunShellProps) {
  const activeIndex = stages.findIndex((stage) => stage.key === activeStage)

  return (
    <div className="flex min-h-full flex-col bg-background lg:h-full lg:min-h-0 lg:overflow-hidden">
      <header className="shrink-0 border-b border-border bg-surface/55">
        <div className="mx-auto flex h-[58px] w-full max-w-[1320px] items-center justify-between gap-4 px-5 sm:px-8">
          <div className="min-w-0">
            <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-primary-light">WOOBE / first run</p>
            <p className="mt-0.5 truncate font-mono text-[12px] font-semibold text-slate-100">Launch your first Agent</p>
          </div>
          <Button type="button" size="sm" variant="outline" onClick={onExit}>
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />Exit setup
          </Button>
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-[1320px] flex-1 gap-4 px-5 py-4 sm:px-8 lg:min-h-0 lg:grid-cols-[218px_minmax(0,1fr)] lg:overflow-hidden">
        <aside className="space-y-3 lg:min-h-0 lg:self-start">
          <SectionBlock title="Launch progress" eyebrow="Sequence" density="compact">
            <div className="divide-y divide-border">
              {stages.map((stage, index) => {
                const completed = index < activeIndex
                const active = index === activeIndex
                return (
                  <div key={stage.key} className="flex items-start gap-2.5 py-2 first:pt-0 last:pb-0">
                    <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-technical border font-mono text-[9px] ${completed ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-300' : active ? 'border-primary/55 bg-primary/10 text-primary-light' : 'border-border bg-control text-muted'}`}>
                      {completed ? <Check className="h-3 w-3" /> : index + 1}
                    </span>
                    <div className="min-w-0">
                      <p className={`font-mono text-[10px] font-medium ${active ? 'text-slate-100' : 'text-muted'}`}>{stage.label}</p>
                      {active ? <p className="mt-0.5 font-sans text-[11px] leading-4 text-muted">{stage.description}</p> : null}
                    </div>
                  </div>
                )
              })}
            </div>
          </SectionBlock>

          <SectionBlock title="Context" density="compact">
            <dl className="space-y-2 font-mono text-[9px]">
              <div><dt className="text-muted">Workspace</dt><dd className="mt-0.5 truncate text-slate-200" title={workspaceName}>{workspaceName}</dd></div>
              <div className="border-t border-border pt-2"><dt className="text-muted">Project</dt><dd className="mt-0.5 truncate text-slate-200" title={projectName || 'Not created yet'}>{projectName || 'Not created yet'}</dd></div>
            </dl>
          </SectionBlock>
        </aside>

        <main className="min-h-0 min-w-0 lg:overflow-hidden">{children}</main>
      </div>
    </div>
  )
}
