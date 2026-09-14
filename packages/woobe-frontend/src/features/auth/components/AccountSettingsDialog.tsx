import { LogOut } from 'lucide-react'
import {
  Alert,
  AlertDescription,
  Button,
  Dialog,
  Field,
  FieldDescription,
  FieldLabel,
  Input,
  SectionBlock,
  TechnicalListItem,
} from '@woobe/ui'
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
    <Dialog open={open} onClose={onClose} title="Account settings" className="max-w-dialog">
      <div className="grid gap-ui-md">
        <SectionBlock
          eyebrow="Personal account"
          title="Identity"
          description="Identity used to access Woobe Workspaces and Projects."
          density="compact"
        >
          <div className="grid gap-ui-md">
            <Field>
              <FieldLabel htmlFor="account-email">Email</FieldLabel>
              <Input id="account-email" value={user?.email || ''} disabled className="font-mono" />
            </Field>

            <Field>
              <FieldLabel>Password</FieldLabel>
              <Button type="button" variant="outline" size="sm" disabled>Change password</Button>
              <FieldDescription>Password management is not available in this interface yet.</FieldDescription>
            </Field>
          </div>
        </SectionBlock>

        <Alert variant="warning">
          <AlertDescription>Signing out ends the current Woobe session on this device.</AlertDescription>
        </Alert>

        <div className="flex flex-col gap-ui-sm border-t border-border pt-ui-md sm:flex-row sm:items-center sm:justify-between">
          <TechnicalListItem
            className="min-w-0 flex-1 border-0 bg-transparent p-0"
            label="Current session"
            description={user?.email || 'Signed in'}
          />
          <Button type="button" variant="destructive" size="sm" onClick={handleSignOut}>
            <LogOut className="h-icon w-icon" />
            Sign out
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
