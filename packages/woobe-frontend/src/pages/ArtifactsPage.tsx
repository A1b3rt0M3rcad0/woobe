import { useNavigate, useSearchParams } from 'react-router-dom'
import { ErrorState } from '@/components/common/ErrorState'
import { useParams } from 'react-router-dom'
import { ArtifactExplorer } from '@/features/artifacts/components/ArtifactExplorer'
import { ArtifactDocumentReader } from '@/features/artifacts/components/ArtifactDocumentReader'
import { ArtifactWorkspaces } from '@/features/artifacts/components/ArtifactWorkspaces'
import type { ArtifactEnvironment } from '@/features/artifacts/types'

const environments: ArtifactEnvironment[] = ['draft', 'staging', 'production']

function readEnvironment(value: string | null): ArtifactEnvironment {
  return environments.includes(value as ArtifactEnvironment) ? value as ArtifactEnvironment : 'draft'
}

export default function ArtifactsPage() {
  const { workspaceId, projectId, artifactWorkspaceId, artifactId, revisionId } = useParams<{
    workspaceId: string
    projectId: string
    artifactWorkspaceId?: string
    artifactId?: string
    revisionId?: string
  }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const environment = readEnvironment(searchParams.get('environment'))

  if (!workspaceId || !projectId) return <ErrorState message="Project not found" />

  const setEnvironment = (next: ArtifactEnvironment) => {
    const updated = new URLSearchParams(searchParams)
    updated.set('environment', next)
    setSearchParams(updated)
  }

  if (artifactWorkspaceId && artifactId && revisionId) {
    return <ArtifactDocumentReader
      key={`${projectId}:${artifactWorkspaceId}:${artifactId}:${revisionId}:${environment}`}
      projectId={projectId}
      workspaceId={artifactWorkspaceId}
      artifactId={artifactId}
      revisionId={revisionId}
      environment={environment}
      accountWorkspaceId={workspaceId}
      onBack={() => navigate(`/workspaces/${workspaceId}/projects/${projectId}/artifacts/${encodeURIComponent(artifactWorkspaceId)}?environment=${environment}`)}
      onSelectRevision={nextRevisionId => navigate(`/workspaces/${workspaceId}/projects/${projectId}/artifacts/${encodeURIComponent(artifactWorkspaceId)}/files/${encodeURIComponent(artifactId)}/revisions/${encodeURIComponent(nextRevisionId)}?environment=${environment}`)}
    />
  }

  return artifactWorkspaceId ? (
    <ArtifactExplorer
      key={`${projectId}:${artifactWorkspaceId}:${environment}`}
      workspaceId={artifactWorkspaceId}
      projectId={projectId}
      environment={environment}
      onEnvironmentChange={setEnvironment}
    />
  ) : (
    <ArtifactWorkspaces
      key={`${projectId}:${environment}`}
      projectId={projectId}
      environment={environment}
      onEnvironmentChange={setEnvironment}
    />
  )
}
