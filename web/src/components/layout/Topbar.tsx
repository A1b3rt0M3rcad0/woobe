import { useAuth } from '@/features/auth/AuthProvider'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { useNavigate } from 'react-router-dom'
import { Boxes, FolderKanban, LogOut } from 'lucide-react'

export function Topbar() {
  const { user, logout } = useAuth()
  const { currentWorkspace, currentProject } = useWorkspace()
  const navigate = useNavigate()

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-surface px-6">
      <div className="flex items-center gap-2 text-sm">
        <button className="flex items-center gap-2 text-muted hover:text-white" onClick={() => navigate('/workspaces')}>
          <Boxes className="h-3.5 w-3.5" />
          <span>{currentWorkspace?.name || 'Workspaces'}</span>
        </button>
        {currentWorkspace && currentProject && (
          <>
            <span className="text-border">/</span>
            <button
              className="flex items-center gap-2 text-white"
              onClick={() => navigate(`/workspaces/${currentWorkspace.id}/projects/${currentProject.id}`)}
            >
              <FolderKanban className="h-3.5 w-3.5" />
              <span>{currentProject.name}</span>
            </button>
          </>
        )}
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted">{user?.email}</span>
        <button onClick={() => void logout()} className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-accent hover:text-white">
          <LogOut className="h-4 w-4" />Logout
        </button>
      </div>
    </header>
  )
}
