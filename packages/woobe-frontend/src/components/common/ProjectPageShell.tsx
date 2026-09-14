import { type ReactNode } from 'react'
import { Badge, PageHeader } from '@woobe/ui'
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

  const context = currentWorkspace || currentProject ? (
    <div className="mt-ui-sm flex flex-wrap gap-ui-xs">
      {currentWorkspace ? <Badge variant="outline" size="compact">Workspace · {currentWorkspace.name}</Badge> : null}
      {currentProject ? <Badge variant="outline" size="compact">Project · {currentProject.name}</Badge> : null}
    </div>
  ) : null

  return (
    <div className={cn('space-y-ui-lg', className)}>
      <PageHeader
        eyebrow={eyebrow}
        title={title}
        actions={actions}
        className="mb-0"
        description={description || context ? <>{description}{context}</> : undefined}
      />
      {children}
    </div>
  )
}
