import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { EmptyState } from '@/components/common/EmptyState'
import { Button } from '@/components/ui/Button'
import { FolderKanban, ArrowRight, Building2 } from 'lucide-react'

export default function ProjectsPage() {
  const { currentOrganization } = useWorkspace()
  const navigate = useNavigate()

  useEffect(() => {
    if (currentOrganization) {
      navigate(`/organizations/${currentOrganization.id}/projects`, { replace: true })
    } else {
      navigate('/organizations', { replace: true })
    }
  }, [currentOrganization, navigate])

  return <LoadingState message="Redirecting..." />
}
