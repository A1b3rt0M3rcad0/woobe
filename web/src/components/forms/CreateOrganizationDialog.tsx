import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'

export function CreateOrganizationDialog() {
  return (
    <Dialog open={false} onClose={() => undefined} title="Create Organization">
      <Button>Create</Button>
    </Dialog>
  )
}
