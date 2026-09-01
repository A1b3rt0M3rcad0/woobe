import { useState, useRef, useEffect } from 'react'
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
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 rounded-lg px-2 py-1 text-sm text-muted hover:text-white transition-colors"
      >
        {trigger}
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div
          className={`absolute top-full mt-1 z-50 min-w-[200px] rounded-lg border border-border bg-surface py-1 shadow-lg ${align === 'right' ? 'right-0' : 'left-0'}`}
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      )}
    </div>
  )
}

export function Topbar() {
  const { user, logout } = useAuth()
  const { currentWorkspace, currentProject, workspaces, projects, selectWorkspace, selectProject, clearCurrentProject } = useWorkspace()
  const navigate = useNavigate()

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-surface px-6">
      <div className="flex items-center gap-2 text-sm">
        <DropdownMenu
          trigger={
            <>
              <Building2 className="h-3.5 w-3.5 shrink-0" />
              <span className={currentWorkspace ? 'text-white' : 'text-primary font-medium'}>
                {currentWorkspace?.name || 'Select workspace'}
              </span>
            </>
          }
        >
          {workspaces.length === 0 ? (
            <div className="px-3 py-2 text-xs text-muted">No workspaces</div>
          ) : (
            workspaces.map((workspace) => (
              <button
                key={workspace.id}
                className={`flex w-full items-center gap-2 px-3 py-1.5 text-sm hover:bg-accent transition-colors ${workspace.id === currentWorkspace?.id ? 'text-white' : 'text-muted'}`}
                onClick={() => {
                  if (workspace.id !== currentWorkspace?.id) {
                    selectWorkspace(workspace)
                    navigate(`/workspaces/${workspace.id}/projects`)
                  }
                }}
              >
                <Building2 className="h-3.5 w-3.5" />
                {workspace.name}
              </button>
            ))
          )}
          <div className="border-t border-border my-1" />
          {currentWorkspace && (
            <button
              className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-muted hover:bg-accent transition-colors"
              onClick={() => navigate(`/workspaces/${currentWorkspace.id}/settings`)}
            >
              <Settings className="h-3.5 w-3.5" />
              Workspace settings
            </button>
          )}
          <button
            className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-muted hover:bg-accent transition-colors"
            onClick={() => navigate('/workspaces')}
          >
            <List className="h-3.5 w-3.5" />
            Manage workspaces
          </button>
          <button
            className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-muted hover:bg-accent transition-colors"
            onClick={() => navigate('/workspaces')}
          >
            <Plus className="h-3.5 w-3.5" />
            Create workspace
          </button>
        </DropdownMenu>

        {currentWorkspace && (
          <>
            <span className="text-border">/</span>
            <DropdownMenu
              trigger={
                <>
                  <FolderKanban className="h-3.5 w-3.5 shrink-0" />
                  <span className={currentProject ? 'text-white' : 'text-primary font-medium'}>
                    {currentProject?.name || 'Select project'}
                  </span>
                </>
              }
            >
              {projects.length === 0 ? (
                <div className="px-3 py-2 text-xs text-muted">No projects</div>
              ) : (
                projects.map((proj) => (
                  <button
                    key={proj.id}
                    className={`flex w-full items-center gap-2 px-3 py-1.5 text-sm hover:bg-accent transition-colors ${proj.id === currentProject?.id ? 'text-white' : 'text-muted'}`}
                    onClick={() => {
                      if (proj.id !== currentProject?.id) {
                        selectProject(proj)
                        navigate(`/workspaces/${currentWorkspace.id}/projects/${proj.id}`)
                      }
                    }}
                  >
                    <FolderKanban className="h-3.5 w-3.5" />
                    {proj.name}
                  </button>
                ))
              )}
              <div className="border-t border-border my-1" />
              {currentProject && (
                <button
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-muted hover:bg-accent transition-colors"
                  onClick={() => navigate(`/workspaces/${currentWorkspace.id}/projects/${currentProject.id}/settings`)}
                >
                  <Settings className="h-3.5 w-3.5" />
                  Project settings
                </button>
              )}
              <button
                className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-muted hover:bg-accent transition-colors"
                onClick={() => navigate(`/workspaces/${currentWorkspace.id}/projects`)}
              >
                <List className="h-3.5 w-3.5" />
                Manage projects
              </button>
              <button
                className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-muted hover:bg-accent transition-colors"
                onClick={() => navigate(`/workspaces/${currentWorkspace.id}/projects`)}
              >
                <Plus className="h-3.5 w-3.5" />
                Create project
              </button>
            </DropdownMenu>
          </>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span className="text-sm text-muted">{user?.email}</span>
        <button
          onClick={logout}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-accent hover:text-white transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Logout
        </button>
      </div>
    </header>
  )
}