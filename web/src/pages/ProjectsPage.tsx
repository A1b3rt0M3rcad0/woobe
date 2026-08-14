import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { EmptyState } from '@/components/common/EmptyState'
import { Button } from '@/components/ui/Button'
import { FolderKanban, ArrowRight, Building2 } from 'lucide-react'

export default function ProjectsPage() {
  const { currentWorkspace } = useWorkspace()
  const navigate = useNavigate()

  useEffect(() => {
    if (currentWorkspace) {
      navigate(`/workspaces/${currentWorkspace.id}/projects`, { replace: true })
    } else {
      navigate('/workspaces', { replace: true })
    }
  }, [currentWorkspace, navigate])

  return <LoadingState message="Redirecting..." />
}
