import { type ReactNode } from 'react'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { cn } from '@/lib/utils'

interface ProjectPageShellProps {
  eyebrow?: string
  title: string
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
}

export function ProjectPageShell({ eyebrow, title, description, actions, children, className }: ProjectPageShellProps) {
  const { currentWorkspace, currentProject } = useWorkspace()

  return (
    <div className={cn('space-y-6', className)}>
      <header className="rounded-2xl border border-border bg-surface/80 p-4 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            {eyebrow && <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary-light">{eyebrow}</p>}
            <h1 className="mt-1 text-2xl font-bold text-white">{title}</h1>
            {description && <div className="mt-2 max-w-3xl text-sm text-muted">{description}</div>}
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted">
              {currentWorkspace && <span className="rounded-full border border-border bg-background px-2.5 py-1">Workspace · {currentWorkspace.name}</span>}
              {currentProject && <span className="rounded-full border border-border bg-background px-2.5 py-1">Project · {currentProject.name}</span>}
            </div>
          </div>
          {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
        </div>
      </header>
      {children}
    </div>
  )
}
