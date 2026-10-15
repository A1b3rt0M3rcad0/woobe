import { Link } from 'react-router-dom'
import { Menu, ChevronRight } from 'lucide-react'
import { Button, WoobeLogo } from '@woobe/ui'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'

/** Context chrome only. Project selection and authority remain with their owners. */
export function Topbar({ onOpenNavigation }: { onOpenNavigation: () => void }) {
  const { currentWorkspace, currentProject } = useWorkspace()
  return (
    <header className="flex h-workspace-header shrink-0 items-center justify-between gap-ui-md border-b border-border bg-surface px-ui-lg sm:px-ui-xxl">
      <div className="flex min-w-0 items-center gap-ui-sm text-product-small">
        <Button variant="ghost" size="iconSm" onClick={onOpenNavigation} aria-label="Open navigation" className="shrink-0 lg:hidden">
          <Menu className="h-icon-lg w-icon-lg" aria-hidden="true" />
        </Button>
        <WoobeLogo variant="mark" decorative className="hidden h-icon-lg lg:inline-flex" />
        <Link to={currentWorkspace ? `/workspaces/${currentWorkspace.id}/projects` : '/workspaces'} className="truncate text-muted-foreground hover:text-foreground">
          {currentWorkspace?.name ?? 'Workspaces'}
        </Link>
        {currentProject && <>
          <ChevronRight className="h-icon-sm w-icon-sm shrink-0 text-muted-foreground" aria-hidden="true" />
          <Link to={`/workspaces/${currentWorkspace?.id}/projects/${currentProject.id}`} className="truncate font-medium text-foreground">{currentProject.name}</Link>
        </>}
      </div>
    </header>
  )
}
