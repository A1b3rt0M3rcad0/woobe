import { useAuth } from '@/features/auth/AuthProvider'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Separator } from '@/components/ui/Separator'
import { LogOut } from 'lucide-react'

export default function SettingsPage() {
  const { user, logout } = useAuth()

  return (
    <div>
      <PageHeader title="Account" description="Manage your personal Woobe account." />

      <Card className="max-w-2xl">
        <CardHeader><CardTitle>Personal account</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Email</label>
            <Input value={user?.email || ''} disabled />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Password</label>
            <Button variant="outline" size="sm" disabled>Change password</Button>
          </div>
          <Separator />
          <Button variant="destructive" size="sm" onClick={logout}>
            <LogOut className="mr-2 h-4 w-4" />
            Sign out
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
