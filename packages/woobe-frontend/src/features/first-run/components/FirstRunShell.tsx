import type { ReactNode } from 'react'
import { ArrowLeft, Check } from 'lucide-react'
import { Button, WoobeLogo } from '@woobe/ui'
import type { AgentCreationStep } from '@/features/agents/hooks/useAgentCreationFlow'

export type FirstRunStage = 'project' | AgentCreationStep | 'test'
interface FirstRunShellProps {
  workspaceName: string
  projectName?: string
  activeStage: FirstRunStage
  onExit: () => void
  busy?: boolean
  children: ReactNode
}
const stages: Array<{ key: FirstRunStage; label: string; description: string }> = [
  { key: 'project', label: 'Project', description: 'A home for your Agent and its resources.' },
  { key: 'details', label: 'Agent instructions', description: 'Give it a name and a clear objective.' },
  { key: 'model', label: 'Model', description: 'Choose the model that will respond.' },
  { key: 'review', label: 'Review', description: 'Check your choices and create a Draft.' },
  { key: 'test', label: 'First test', description: 'Send a message in the Playground.' },
]
export function FirstRunShell({ workspaceName, projectName, activeStage, onExit, busy, children }: FirstRunShellProps) {
  const activeIndex = stages.findIndex(stage => stage.key === activeStage)
  return (
    <div className="min-h-full bg-background">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex w-full max-w-[1120px] items-center justify-between gap-4 px-5 py-5 sm:px-8">
          <div className="min-w-0">
            <div className="mb-2 flex items-center gap-2 text-sm text-muted-foreground"><WoobeLogo variant="mark" decorative className="h-4 shrink-0" /><span>First Agent setup</span></div>
            <h1 className="font-serif text-editorial-section font-normal text-foreground">Create your first Agent</h1>
            <p className="mt-2 max-w-xl text-sm leading-5 text-muted-foreground">Define what it does, connect a model and try it in the Playground.</p>
          </div>
          <Button type="button" size="sm" variant="outline" onClick={onExit} disabled={busy} className="shrink-0"><ArrowLeft className="h-3.5 w-3.5" />Exit setup</Button>
        </div>
      </header>
      <div className="mx-auto grid w-full max-w-[1120px] items-start gap-6 px-5 py-6 sm:px-8 lg:grid-cols-[208px_minmax(0,1fr)]">
        <aside className="min-w-0 space-y-6">
          <nav aria-label="Setup progress"><ol className="flex flex-wrap gap-x-5 gap-y-3 lg:block lg:space-y-5">
            {stages.map((stage, index) => {
              const completed = index < activeIndex
              const active = index === activeIndex
              return <li key={stage.key} aria-current={active ? 'step' : undefined} className="flex items-start gap-3">
                <span aria-hidden="true" className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-control border font-mono text-xs ${completed ? 'border-success/40 bg-success/10 text-success' : active ? 'border-primary bg-primary/10 text-primary-light' : 'border-border bg-surface text-muted-foreground'}`}>{completed ? <Check className="h-3.5 w-3.5" /> : index + 1}</span>
                <div className="min-w-0 pt-0.5"><p className={`text-sm ${active ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>{stage.label}{completed && <span className="sr-only"> completed</span>}</p><p className="mt-1 hidden text-xs leading-5 text-muted-foreground lg:block">{stage.description}</p></div>
              </li>
            })}
          </ol></nav>
          <dl className="hidden space-y-3 border-t border-border pt-4 text-sm lg:block">
            <div><dt className="text-xs text-muted-foreground">Workspace</dt><dd className="mt-1 break-words text-foreground">{workspaceName}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Project</dt><dd className="mt-1 break-words text-foreground">{projectName || 'Created in the first step'}</dd></div>
          </dl>
          <p className="break-words text-sm text-muted-foreground lg:hidden">{workspaceName}{projectName ? ` / ${projectName}` : ''}</p>
        </aside>
        <div className="min-w-0">{children}</div>
      </div>
    </div>
  )
}
