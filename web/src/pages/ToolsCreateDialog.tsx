import { Dialog } from '@/components/ui/Dialog'
import { ApiFirstToolForm, type ApiFirstToolFormSubmitValue } from '@/features/tools/components/ApiFirstToolForm'
import { useCreateTool } from '@/features/tools/hooks'
import { toast } from 'sonner'

interface ToolsCreateDialogProps {
  open: boolean
  projectId: string
  onClose: () => void
}

export function ToolsCreateDialog({ open, projectId, onClose }: ToolsCreateDialogProps) {
  const createTool = useCreateTool()

  const handleSubmit = async (value: ApiFirstToolFormSubmitValue) => {
    await createTool.mutateAsync({ project_id: projectId, ...value })
    toast.success('Tool created')
    onClose()
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create Tool">
      <ApiFirstToolForm
        key={open ? 'tools-page-tool-form-open' : 'tools-page-tool-form-closed'}
        submitLabel="Create"
        loading={createTool.isPending}
        onSubmit={handleSubmit}
        onCancel={onClose}
      />
    </Dialog>
  )
}
