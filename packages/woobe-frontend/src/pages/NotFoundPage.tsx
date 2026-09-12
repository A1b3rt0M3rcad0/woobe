import { useNavigate } from 'react-router-dom'
import { EmptyStatePanel } from '@woobe/ui'
import { Button } from '@/components/ui/Button'

export default function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <EmptyStatePanel
        className="w-full max-w-md border-solid bg-surface/70"
        title={<span className="text-primary-light">404 / route not found</span>}
        description="This route does not exist in the current Woobe control plane surface."
        action={<Button onClick={() => navigate('/dashboard')}>Back to dashboard</Button>}
      />
    </div>
  )
}
