import { LogOut, Settings } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthProvider'

function getInitials(email?: string) {
  if (!email) return 'U'
  const name = email.split('@')[0] || email
  return name
    .split(/[._-]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'U'
}

export function SidebarUserCard({ variant = 'default' }: { variant?: 'default' | 'technical' }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleSignOut() {
    await logout()
    window.location.replace('/login')
  }

  if (variant === 'technical') {
    return (
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2 rounded-container border border-border bg-surface p-2">
          <button
            type="button"
            className="group flex min-w-0 flex-1 items-center gap-2.5 text-left focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
            onClick={() => navigate('/settings')}
            aria-label="Open account settings"
          >
            <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full border border-primary/30 bg-control font-mono text-[9px] font-bold text-slate-100">
              {getInitials(user?.email)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[11px] font-medium text-slate-100">{user?.email?.split('@')[0] || 'User'}</p>
              <p className="mt-0.5 truncate text-[9px] text-muted-foreground">{user?.email || 'Signed in'}</p>
            </div>
            <Settings className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-slate-100" />
          </button>
          <button
            type="button"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-technical border border-border bg-control text-muted-foreground transition-colors hover:border-slate-600 hover:text-slate-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
            onClick={handleSignOut}
            aria-label="Log out"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="border-t border-border p-3">
      <div className="group flex items-center gap-2 rounded-xl border border-border/80 bg-background/60 p-2 transition-colors hover:border-primary/20 hover:bg-background/75">
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-3 rounded-lg p-0.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
          onClick={() => navigate('/settings')}
          aria-label="Open account settings"
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-primary/25 bg-primary/10 text-xs font-semibold text-primary-light">
            {getInitials(user?.email)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{user?.email?.split('@')[0] || 'User'}</p>
            <p className="truncate text-xs text-muted">{user?.email || 'Signed in'}</p>
          </div>
          <Settings className="h-3.5 w-3.5 shrink-0 text-muted transition-colors group-hover:text-white" />
        </button>
        <button
          type="button"
          className="rounded-lg p-1.5 text-muted transition-colors hover:bg-accent hover:text-white"
          onClick={handleSignOut}
          aria-label="Log out"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
