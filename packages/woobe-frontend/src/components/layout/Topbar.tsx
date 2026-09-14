import { useState, useRef, useEffect } from 'react'
import { Button } from '@woobe/ui'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthProvider'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { LogOut, Building2, FolderKanban, ChevronDown, Settings, List, Plus } from 'lucide-react'

function DropdownMenu({
  trigger,
  children,
  align = 'left',
}: {
  trigger: React.ReactNode
  children: React.ReactNode
  align?: 'left' | 'right'
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex h-control-sm items-center gap-ui-xs rounded-control border border-transparent px-ui-sm font-mono text-system-control text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50"
      >
        {trigger}
        <ChevronDown className={`h-icon-sm w-icon-sm transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div
          className={`absolute top-full z-popover mt-ui-xs min-w-popover rounded-container border border-border bg-surface py-ui-xs shadow-popup ${align === 'right' ? 'right-0' : 'left-0'}`}
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      )}
    </div>
  )
}

const menuItemClass = 'flex min-h-control-sm w-full items-center gap-ui-sm px-ui-md py-ui-sm text-left font-mono text-system-control text-muted-foreground transition-colors hover:bg-accent hover:text-slate-50'

export function Topbar() {
  const { user, logout } = useAuth()
  const { currentWorkspace, currentProject, workspaces, projects, selectWorkspace, selectProject } = useWorkspace()
  const navigate = useNavigate()

  return (
    <header className="flex h-workspace-header items-center justify-between border-b border-border bg-surface px-ui-xxl">
      <div className="flex items-center gap-ui-sm">
        <DropdownMenu
          trigger={
            <>
              <Building2 className="h-icon w-icon shrink-0" />
              <span className={currentWorkspace ? 'text-slate-50' : 'font-medium text-primary-light'}>
                {currentWorkspace?.name || 'Select workspace'}
              </span>
            </>
          }
        >
          {workspaces.length === 0 ? (
            <div className="px-ui-md py-ui-sm font-sans text-product-caption text-muted-foreground">No workspaces</div>
          ) : (
            workspaces.map((workspace) => (
              <button
                key={workspace.id}
                type="button"
                className={`${menuItemClass} ${workspace.id === currentWorkspace?.id ? 'bg-primary/[0.08] text-slate-50' : ''}`}
                onClick={() => {
                  if (workspace.id !== currentWorkspace?.id) {
                    selectWorkspace(workspace)
                    navigate(`/workspaces/${workspace.id}/projects`)
                  }
                }}
              >
                <Building2 className="h-icon w-icon" />
                {workspace.name}
              </button>
            ))
          )}
          <div className="my-ui-xs border-t border-border" />
          {currentWorkspace && (
            <button type="button" className={menuItemClass} onClick={() => navigate(`/workspaces/${currentWorkspace.id}/settings`)}>
              <Settings className="h-icon w-icon" />
              Workspace settings
            </button>
          )}
          <button type="button" className={menuItemClass} onClick={() => navigate('/workspaces')}>
            <List className="h-icon w-icon" />
            Manage workspaces
          </button>
          <button type="button" className={menuItemClass} onClick={() => navigate('/workspaces')}>
            <Plus className="h-icon w-icon" />
            Create workspace
          </button>
        </DropdownMenu>

        {currentWorkspace && (
          <>
            <span className="font-mono text-system-meta text-border">/</span>
            <DropdownMenu
              trigger={
                <>
                  <FolderKanban className="h-icon w-icon shrink-0" />
                  <span className={currentProject ? 'text-slate-50' : 'font-medium text-primary-light'}>
                    {currentProject?.name || 'Select project'}
                  </span>
                </>
              }
            >
              {projects.length === 0 ? (
                <div className="px-ui-md py-ui-sm font-sans text-product-caption text-muted-foreground">No projects</div>
              ) : (
                projects.map((proj) => (
                  <button
                    key={proj.id}
                    type="button"
                    className={`${menuItemClass} ${proj.id === currentProject?.id ? 'bg-primary/[0.08] text-slate-50' : ''}`}
                    onClick={() => {
                      if (proj.id !== currentProject?.id) {
                        selectProject(proj)
                        navigate(`/workspaces/${currentWorkspace.id}/projects/${proj.id}`)
                      }
                    }}
                  >
                    <FolderKanban className="h-icon w-icon" />
                    {proj.name}
                  </button>
                ))
              )}
              <div className="my-ui-xs border-t border-border" />
              {currentProject && (
                <button type="button" className={menuItemClass} onClick={() => navigate(`/workspaces/${currentWorkspace.id}/projects/${currentProject.id}/settings`)}>
                  <Settings className="h-icon w-icon" />
                  Project settings
                </button>
              )}
              <button type="button" className={menuItemClass} onClick={() => navigate(`/workspaces/${currentWorkspace.id}/projects`)}>
                <List className="h-icon w-icon" />
                Manage projects
              </button>
              <button type="button" className={menuItemClass} onClick={() => navigate(`/workspaces/${currentWorkspace.id}/projects`)}>
                <Plus className="h-icon w-icon" />
                Create project
              </button>
            </DropdownMenu>
          </>
        )}
      </div>

      <div className="flex items-center gap-ui-md">
        <span className="font-mono text-system-control text-muted-foreground">{user?.email}</span>
        <Button type="button" variant="ghost" size="sm" onClick={logout} className="text-muted-foreground">
          <LogOut className="h-icon w-icon" />
          Logout
        </Button>
      </div>
    </header>
  )
}
