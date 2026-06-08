import { useNavigate, useParams } from 'react-router-dom'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { PageHeader } from '@/components/common/PageHeader'
import { EmptyState } from '@/components/common/EmptyState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import {
  Building2, FolderKanban, Bot, BookOpen, Wrench, Key, BarChart3, Activity,
  ArrowRight, Play, Upload,
} from 'lucide-react'
import { orgProjectPath } from '@/lib/constants/routes'

const overviewCards = [
  { label: 'Agents', icon: Bot, segment: 'agents', color: 'text-primary' },
  { label: 'Knowledge', icon: BookOpen, segment: 'knowledge', color: 'text-emerald-400' },
  { label: 'Tools', icon: Wrench, segment: 'tools', color: 'text-yellow-400' },
  { label: 'API Keys', icon: Key, segment: 'api-keys', color: 'text-purple-400' },
  { label: 'Usage', icon: BarChart3, segment: 'usage', color: 'text-orange-400' },
  { label: 'Traces', icon: Activity, segment: 'traces', color: 'text-cyan-400' },
]

const quickActions = [
  { label: 'Create agent', icon: Bot, path: (o: string, p: string) => orgProjectPath(o, p, 'agents', 'new') },
  { label: 'Open playground', icon: Play, path: (o: string, p: string) => orgProjectPath(o, p, 'agents') },
  { label: 'Upload document', icon: Upload, path: (o: string, p: string) => orgProjectPath(o, p, 'knowledge') },
  { label: 'Create API key', icon: Key, path: (o: string, p: string) => orgProjectPath(o, p, 'api-keys') },
]

export default function DashboardPage() {
  const { currentOrganization, currentProject } = useWorkspace()
  const params = useParams<{ organizationId?: string; projectId?: string }>()
  const navigate = useNavigate()

  if (!currentOrganization) {
    return (
      <div>
        <PageHeader title="Dashboard" description="Select an organization to continue." />
        <EmptyState
          icon={<Building2 className="h-12 w-12" />}
          title="No organization selected"
          description="Select or create an organization to get started."
          action={
            <Button onClick={() => navigate('/organizations')}>
              <Building2 className="mr-2 h-4 w-4" />
              Select organization
            </Button>
          }
        />
      </div>
    )
  }

  if (!currentProject) {
    return (
      <div>
        <PageHeader
          title="Dashboard"
          description={`Organization: ${currentOrganization.name}`}
        />
        <EmptyState
          icon={<FolderKanban className="h-12 w-12" />}
          title="No project selected"
          description="Select or create a project to continue."
          action={
            <Button onClick={() => navigate(`/organizations/${currentOrganization.id}/projects`)}>
              <FolderKanban className="mr-2 h-4 w-4" />
              Select project
            </Button>
          }
        />
      </div>
    )
  }

  const oid = currentOrganization.id
  const pid = currentProject.id

  return (
    <div>
      <PageHeader
        title={currentProject.name}
        description="Project overview and quick actions."
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {overviewCards.map((card) => (
          <Card
            key={card.label}
            className="cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => navigate(orgProjectPath(oid, pid, card.segment))}
          >
            <CardContent className="flex items-center justify-between p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <card.icon className={`h-5 w-5 ${card.color}`} />
                </div>
                <span className="font-medium text-white">{card.label}</span>
              </div>
              <ArrowRight className="h-4 w-4 text-muted" />
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Quick actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            {quickActions.map((action) => (
              <Button
                key={action.label}
                variant="outline"
                onClick={() => navigate(action.path(oid, pid))}
              >
                <action.icon className="mr-2 h-4 w-4" />
                {action.label}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}