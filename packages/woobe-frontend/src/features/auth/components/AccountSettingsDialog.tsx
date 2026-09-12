import { LogOut } from 'lucide-react'
import { Button, Dialog, Field, FieldDescription, FieldLabel, Input } from '@woobe/ui'
import { useAuth } from '@/features/auth/AuthProvider'

interface AccountSettingsDialogProps {
  open: boolean
  onClose: () => void
}

export function AccountSettingsDialog({ open, onClose }: AccountSettingsDialogProps) {
  const { user, logout } = useAuth()

  async function handleSignOut() {
    await logout()
    window.location.replace('/login')
  }

  return (
    <Dialog open={open} onClose={onClose} title="Account settings" className="max-w-[460px]">
      <div className="space-y-4">
        <div className="border-b border-border pb-3">
          <p className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-slate-100">Personal account</p>
          <p className="mt-1 font-mono text-[8px] leading-4 text-muted-foreground">Identity used to access Woobe workspaces and projects.</p>
        </div>

        <Field>
          <FieldLabel htmlFor="account-email">Email</FieldLabel>
          <Input id="account-email" value={user?.email || ''} disabled className="font-mono text-[10px]" />
        </Field>

        <Field>
          <FieldLabel>Password</FieldLabel>
          <Button type="button" variant="outline" size="sm" disabled>Change password</Button>
          <FieldDescription>Password management is not available in this interface yet.</FieldDescription>
        </Field>

        <div className="flex items-center justify-between gap-3 border-t border-border pt-4">
          <p className="font-mono text-[8px] text-muted-foreground">Signing out ends the current Woobe session.</p>
          <Button type="button" variant="destructive" size="sm" onClick={handleSignOut}>
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
