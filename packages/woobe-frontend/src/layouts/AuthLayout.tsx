import { Outlet } from 'react-router-dom'
import { Orbit, GitBranch, FlaskConical, Activity } from 'lucide-react'

const lifecycle = [
  { icon: GitBranch, title: 'Define', description: 'Version agents, instructions and connected resources.' },
  { icon: FlaskConical, title: 'Validate', description: 'Evaluate a configuration before it reaches production.' },
  { icon: Activity, title: 'Operate', description: 'Follow every Run, release and execution trace.' },
]

export function AuthLayout() {
  return (
    <main className="grid min-h-svh bg-background lg:grid-cols-2">
      <section className="relative hidden flex-col justify-between overflow-hidden bg-background p-12 text-foreground lg:flex xl:p-16" aria-label="About Woobe">
        <div className="flex items-center gap-ui-md" translate="no">
          <Orbit className="h-8 w-8" strokeWidth={1.6} aria-hidden="true" />
          <span className="text-brand-title font-semibold tracking-tight">Woobe</span>
        </div>
        <div className="relative my-16 max-w-lg">
          <p className="mb-6 text-product-small text-muted-foreground">Your agents. Your infrastructure.</p>
          <h2 className="font-serif text-5xl font-normal leading-[1.04] tracking-[-0.04em] xl:text-6xl">From a first draft<br />to production.</h2>
          <p className="mt-6 max-w-sm font-sans text-product-reading leading-relaxed text-muted-foreground">One control plane to define, test and operate AI agents with a record of what happened.</p>
          <div className="mt-12 rounded-container border border-border bg-surface shadow-panel">
            {lifecycle.map(({ icon: Icon, title, description }) => (
              <div key={title} className="flex items-start gap-4 border-b border-border px-ui-panel-inset py-ui-lg last:border-b-0">
                <Icon className="mt-1 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <div><h3 className="font-mono text-product-body font-medium">{title}</h3><p className="mt-1 text-product-small text-muted-foreground">{description}</p></div>
              </div>
            ))}
          </div>
        </div>
        <p className="text-product-caption text-muted-foreground">Self-hostable. API-first. Built around your workflow.</p>
      </section>
      <section className="flex min-w-0 flex-col justify-center border-l border-border bg-surface px-6 py-12 sm:px-12 lg:px-16">
        <div className="mx-auto w-full max-w-form-narrow">
          <div className="mb-12 flex items-center gap-ui-sm text-foreground lg:hidden" translate="no"><Orbit className="h-7 w-7" aria-hidden="true" /><span className="text-brand-title font-semibold">Woobe</span></div>
          <Outlet />
          <p className="mt-10 border-t border-border pt-5 text-product-caption text-muted-foreground">Control plane for production AI agents</p>
        </div>
      </section>
    </main>
  )
}
