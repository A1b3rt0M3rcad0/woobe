import { useNavigate, useParams } from 'react-router-dom'
import { Card } from '@woobe/ui'
import { WorkspaceSettingsDialog } from '@/features/workspaces/components/WorkspaceSettingsDialog'

export default function WorkspaceDetailPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const navigate = useNavigate()

  if (!workspaceId) {
    return (
      <Card className="mx-auto max-w-lg border-error/30 bg-error/[0.05] px-6 py-10 text-center">
        <p className="font-mono text-[10px] font-bold text-red-200">Workspace not found</p>
      </Card>
    )
  }

  return (
    <WorkspaceSettingsDialog
      open
      workspaceId={workspaceId}
      onClose={() => navigate(`/workspaces/${workspaceId}/projects`, { replace: true })}
    />
  )
}
