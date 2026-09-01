import type { ReactNode } from 'react'
import { ArrowLeft, Check, Rocket } from 'lucide-react'

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
  { key: 'project', label: 'Project', description: 'Create the technical workspace.' },
  { key: 'agent', label: 'Agent', description: 'Configure the first operational Agent.' },
  { key: 'test', label: 'First test', description: 'Run the Agent in the Playground.' },
]

export function FirstRunShell({
  workspaceName,
  projectName,
  activeStage,
  onExit,
  children,
}: FirstRunShellProps) {
  const activeIndex = stages.findIndex((stage) => stage.key === activeStage)

  return (
    <div className="flex min-h-full flex-col bg-background lg:h-full lg:min-h-0 lg:overflow-hidden">
      <header className="shrink-0 border-b border-border/80 bg-surface/45">
        <div className="mx-auto flex w-full max-w-[1240px] items-start justify-between gap-6 px-5 py-5 sm:px-8 lg:px-10 lg:py-6">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary/[0.06] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.16em] text-primary-light">
              <Rocket className="h-3.5 w-3.5" />
              First run setup
            </div>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight text-white">Launch your first Agent</h1>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-muted">
              Create the Project boundary, configure the Agent and continue directly to its first Playground test.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={onExit}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Exit setup
          </Button>
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-[1240px] flex-1 gap-6 px-5 py-5 sm:px-8 lg:min-h-0 lg:grid-cols-[232px_minmax(0,1fr)] lg:overflow-hidden lg:px-10 lg:py-6">
        <aside className="space-y-4 lg:min-h-0 lg:self-start">
          <section className="rounded-xl border border-border/90 bg-surface/65 p-5">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Launch progress</p>
            <div className="mt-5 space-y-4">
              {stages.map((stage, index) => {
                const completed = index < activeIndex
                const active = index === activeIndex
                return (
                  <div key={stage.key} className="flex items-start gap-3">
                    <span
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${
                        completed
                          ? 'border-primary/50 bg-primary/15 text-primary-light'
                          : active
                            ? 'border-primary bg-primary/10 text-white'
                            : 'border-border bg-background text-muted'
                      }`}
                    >
                      {completed ? <Check className="h-4 w-4" /> : index + 1}
                    </span>
                    <div className="min-w-0 pt-0.5">
                      <p className={`text-sm ${active ? 'font-medium text-white' : completed ? 'text-white/85' : 'text-muted'}`}>
                        {stage.label}
                      </p>
                      {active && <p className="mt-0.5 text-xs leading-5 text-muted">{stage.description}</p>}
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          <section className="rounded-xl border border-border/90 bg-background/55 p-5">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Context</p>
            <div className="mt-4 space-y-4">
              <div>
                <p className="text-xs text-muted">Workspace</p>
                <p className="mt-1 truncate text-sm font-medium text-white" title={workspaceName}>{workspaceName}</p>
              </div>
              <div className="h-px bg-border/80" />
              <div>
                <p className="text-xs text-muted">Project</p>
                <p className="mt-1 truncate text-sm font-medium text-white" title={projectName || 'Not created yet'}>
                  {projectName || 'Not created yet'}
                </p>
              </div>
            </div>
          </section>
        </aside>

        <main className="min-h-0 min-w-0 lg:overflow-hidden">{children}</main>
      </div>
    </div>
  )
}
