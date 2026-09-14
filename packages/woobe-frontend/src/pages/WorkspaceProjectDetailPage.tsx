import { useNavigate, useParams } from 'react-router-dom'
import { Card } from '@woobe/ui'
import { ProjectSettingsDialog } from '@/features/projects/components/ProjectSettingsDialog'

export default function WorkspaceProjectDetailPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>()
  const navigate = useNavigate()

  if (!workspaceId || !projectId) {
    return (
      <Card className="mx-auto max-w-lg border-error/30 bg-error/[0.05] px-6 py-10 text-center">
        <p className="font-mono text-[10px] font-bold text-red-200">Project not found</p>
      </Card>
    )
  }

  return (
    <ProjectSettingsDialog
      open
      workspaceId={workspaceId}
      projectId={projectId}
      onClose={() => navigate(`/workspaces/${workspaceId}/projects/${projectId}`, { replace: true })}
    />
  )
}
