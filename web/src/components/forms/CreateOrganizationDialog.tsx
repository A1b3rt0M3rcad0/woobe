import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'

interface CreateOrganizationDialogProps {
  open: boolean
  onClose: () => void
}

export function CreateOrganizationDialog({ open, onClose }: CreateOrganizationDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} title="Create Organization">
      <Button>Create</Button>
    </Dialog>
  )
}
