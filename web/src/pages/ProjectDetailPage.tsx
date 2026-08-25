import { useParams, useNavigate, Link } from 'react-router-dom'
import { useProject } from '@/features/projects/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Bot, BookOpen, Wrench, Key, BarChart3, Activity, Play, ArrowRight } from 'lucide-react'
import { workspaceProjectPath } from '@/lib/constants/routes'

const quickLinks = [
  { label: 'Agents', icon: Bot, segment: 'agents', color: 'text-primary' },
  { label: 'Knowledge', icon: BookOpen, segment: 'knowledge', color: 'text-emerald-400' },
  { label: 'Tools', icon: Wrench, segment: 'tools', color: 'text-yellow-400' },
  { label: 'API Keys', icon: Key, segment: 'api-keys', color: 'text-purple-400' },
  { label: 'Usage', icon: BarChart3, segment: 'usage', color: 'text-orange-400' },
  { label: 'Traces', icon: Activity, segment: 'traces', color: 'text-cyan-400' },
]

export default function ProjectDetailPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId?: string; projectId: string }>()
  const navigate = useNavigate()
  const { data: project, isLoading, isError, error, refetch } = useProject(projectId)

  const p = (projId: string, ...segments: string[]) => workspaceProjectPath(workspaceId, projId, ...segments)

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />
  if (!project) return <ErrorState message="Project not found" />

  return (
    <div>
      <PageHeader
        title={project.name}
        description={`/${project.slug} · ${project.status || 'active'}`}
        actions={
          <Button onClick={() => navigate(p(projectId!, 'agents'))}>
            <Play className="mr-2 h-4 w-4" />
            Open Playground
          </Button>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {quickLinks.map((link) => (
          <Link key={link.label} to={p(projectId!, link.segment)}>
            <Card className="cursor-pointer hover:border-primary/50 transition-colors h-full">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <link.icon className={`h-5 w-5 ${link.color}`} />
                    {link.label}
                  </span>
                  <ArrowRight className="h-4 w-4 text-muted" />
                </CardTitle>
                <CardDescription>Configure and manage {link.label.toLowerCase()}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
