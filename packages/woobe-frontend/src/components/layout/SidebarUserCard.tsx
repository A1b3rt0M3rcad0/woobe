import { useState } from 'react'
import { LogOut, Settings } from 'lucide-react'
import { useAuth } from '@/features/auth/AuthProvider'
import { AccountSettingsDialog } from '@/features/auth/components/AccountSettingsDialog'

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
  const [showAccount, setShowAccount] = useState(false)

  async function handleSignOut() {
    await logout()
    window.location.replace('/login')
  }

  const accountDialog = <AccountSettingsDialog open={showAccount} onClose={() => setShowAccount(false)} />

  if (variant === 'technical') {
    return (
      <>
        <div className="border-t border-border p-ui-md">
          <div className="flex items-center gap-ui-sm rounded-container border border-border bg-surface p-ui-sm">
            <button
              type="button"
              className="group flex min-w-0 flex-1 items-center gap-ui-sm text-left focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
              onClick={() => setShowAccount(true)}
              aria-label="Open account settings"
            >
              <div className="flex h-control-sm w-control-sm shrink-0 items-center justify-center rounded-control border border-primary/30 bg-control font-mono text-system-label font-bold text-slate-100">
                {getInitials(user?.email)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-mono text-system-control font-medium text-slate-100">{user?.email?.split('@')[0] || 'User'}</p>
                <p className="mt-ui-xs truncate font-mono text-system-meta text-muted-foreground">{user?.email || 'Signed in'}</p>
              </div>
              <Settings className="h-icon w-icon shrink-0 text-muted-foreground transition-colors group-hover:text-slate-100" />
            </button>
            <button
              type="button"
              className="flex h-control-segment w-control-segment shrink-0 items-center justify-center rounded-technical border border-border bg-control text-muted-foreground transition-colors hover:border-slate-600 hover:text-slate-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
              onClick={handleSignOut}
              aria-label="Log out"
            >
              <LogOut className="h-icon w-icon" />
            </button>
          </div>
        </div>
        {accountDialog}
      </>
    )
  }

  return (
    <>
      <div className="border-t border-border p-ui-md">
        <div className="group flex items-center gap-ui-sm rounded-container border border-border bg-surface p-ui-sm transition-colors hover:border-slate-600">
          <button
            type="button"
            className="flex min-w-0 flex-1 items-center gap-ui-md rounded-control p-ui-hairline text-left focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
            onClick={() => setShowAccount(true)}
            aria-label="Open account settings"
          >
            <div className="flex h-control w-control shrink-0 items-center justify-center rounded-control border border-primary/25 bg-control font-mono text-system-label font-semibold text-primary-light">
              {getInitials(user?.email)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-system-control font-medium text-slate-100">{user?.email?.split('@')[0] || 'User'}</p>
              <p className="truncate font-mono text-system-meta text-muted-foreground">{user?.email || 'Signed in'}</p>
            </div>
            <Settings className="h-icon w-icon shrink-0 text-muted-foreground transition-colors group-hover:text-slate-100" />
          </button>
          <button
            type="button"
            className="flex h-control-segment w-control-segment items-center justify-center rounded-technical border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-100"
            onClick={handleSignOut}
            aria-label="Log out"
          >
            <LogOut className="h-icon w-icon" />
          </button>
        </div>
      </div>
      {accountDialog}
    </>
  )
}
