import { ChevronRight, LogOut } from 'lucide-react'
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

export function SidebarUserCard() {
  const { user, logout } = useAuth()

  return (
    <div className="border-t border-border p-3">
      <div className="flex items-center gap-3 rounded-xl border border-border bg-background/70 p-2.5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-white">
          {getInitials(user?.email)}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-white">{user?.email?.split('@')[0] || 'User'}</p>
          <p className="truncate text-xs text-muted">{user?.email || 'Signed in'}</p>
        </div>
        <button
          type="button"
          className="rounded-lg p-1.5 text-muted transition-colors hover:bg-accent hover:text-white"
          onClick={logout}
          aria-label="Log out"
        >
          <LogOut className="h-4 w-4" />
        </button>
        <ChevronRight className="hidden h-4 w-4 text-muted" />
      </div>
    </div>
  )
}
