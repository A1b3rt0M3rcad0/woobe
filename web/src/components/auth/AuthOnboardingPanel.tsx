import { Bot, Building2, FolderKanban } from 'lucide-react'

const steps = [
  { icon: Building2, title: 'Create a workspace', description: 'Group members, billing and projects.' },
  { icon: FolderKanban, title: 'Create a project', description: 'Isolate agents, knowledge, tools and keys.' },
  { icon: Bot, title: 'Build agents', description: 'Configure models, instructions and integrations.' },
]

export function AuthOnboardingPanel() {
  return (
    <section className="hidden border-r border-border bg-surface/60 p-10 lg:flex lg:flex-col lg:justify-between">
      <div>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-white">P</div>
          <div>
            <h1 className="text-xl font-bold text-white">ProjectRAI</h1>
            <p className="text-sm text-muted">Production runtime for AI agents</p>
          </div>
        </div>
        <div className="mt-16 max-w-xl">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary-light">Workspace setup</p>
          <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">Build a production AI agent in one guided flow.</h2>
          <p className="mt-4 text-sm leading-6 text-muted">Sign in, choose your workspace, configure an agent and connect the resources it needs to run.</p>
        </div>
      </div>
      <div className="grid gap-3">
        {steps.map((step, index) => (
          <div key={step.title} className="flex items-start gap-3 rounded-2xl border border-border bg-background/70 p-4">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary-light">
              <step.icon className="h-4 w-4" />
            </div>
            <div>
              <p className="text-xs text-primary-light">Step {index + 1}</p>
              <p className="text-sm font-semibold text-white">{step.title}</p>
              <p className="mt-1 text-xs text-muted">{step.description}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
