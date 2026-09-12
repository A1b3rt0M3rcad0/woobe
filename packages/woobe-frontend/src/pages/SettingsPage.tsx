import { useNavigate } from 'react-router-dom'
import { AccountSettingsDialog } from '@/features/auth/components/AccountSettingsDialog'

export default function SettingsPage() {
  const navigate = useNavigate()

  return (
    <AccountSettingsDialog
      open
      onClose={() => navigate('/workspaces', { replace: true })}
    />
  )
}
