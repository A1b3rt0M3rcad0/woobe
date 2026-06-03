import { useAuth } from '@/features/auth/AuthProvider'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Separator } from '@/components/ui/Separator'
import { Tabs } from '@/components/ui/Tabs'
import { LogOut, AlertTriangle } from 'lucide-react'

export default function SettingsPage() {
  const { user, logout } = useAuth()
  const { currentOrganization, currentProject } = useWorkspace()

  const tabs = [
    {
      id: 'user',
      label: 'User',
      content: (
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Account</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-muted mb-1">Email</label>
                <Input value={user?.email || ''} disabled />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted mb-1">Password</label>
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
      ),
    },
    {
      id: 'organization',
      label: 'Organization',
      content: (
        <Card>
          <CardHeader><CardTitle>Organization</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between"><span className="text-sm text-muted">Name</span><span className="text-sm">{currentOrganization?.name || '—'}</span></div>
            <div className="flex justify-between"><span className="text-sm text-muted">Slug</span><span className="text-sm">/{currentOrganization?.slug || '—'}</span></div>
          </CardContent>
        </Card>
      ),
    },
    {
      id: 'project',
      label: 'Project',
      content: (
        <Card>
          <CardHeader><CardTitle>Project</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between"><span className="text-sm text-muted">Name</span><span className="text-sm">{currentProject?.name || 'No project selected'}</span></div>
            <div className="flex justify-between"><span className="text-sm text-muted">Slug</span><span className="text-sm">/{currentProject?.slug || '—'}</span></div>
          </CardContent>
        </Card>
      ),
    },
    {
      id: 'danger',
      label: 'Danger Zone',
      content: (
        <Card className="border-red-500/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="h-5 w-5" />
              Danger Zone
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm font-medium text-white">Revoke API Keys</p>
              <p className="text-sm text-muted mt-1">Revoke all API keys for this project.</p>
              <Button variant="destructive" size="sm" className="mt-2" disabled>Revoke all keys</Button>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm font-medium text-white">Disable Project</p>
              <p className="text-sm text-muted mt-1">Temporarily disable this project.</p>
              <Button variant="destructive" size="sm" className="mt-2" disabled>Disable</Button>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm font-medium text-white">Delete Project</p>
              <p className="text-sm text-muted mt-1">Permanently delete this project and all data.</p>
              <Button variant="destructive" size="sm" className="mt-2" disabled>Delete</Button>
            </div>
          </CardContent>
        </Card>
      ),
    },
  ]

  return (
    <div>
      <PageHeader title="Settings" description="Manage your account, organization, and project settings" />
      <Tabs tabs={tabs} />
    </div>
  )
}
