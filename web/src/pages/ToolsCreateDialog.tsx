import { Dialog } from '@/components/ui/Dialog'
import { ToolDiscoveryForm, type ToolFormSubmitValue } from '@/features/tools/components/ToolDiscoveryForm'
import { useCreateTool, useTestTool } from '@/features/tools/hooks'
import { toast } from 'sonner'

interface ToolsCreateDialogProps {
  open: boolean
  projectId: string
  onClose: () => void
}

export function ToolsCreateDialog({ open, projectId, onClose }: ToolsCreateDialogProps) {
  const createTool = useCreateTool()
  const testTool = useTestTool()

  const handleSubmit = async (value: ToolFormSubmitValue) => {
    await createTool.mutateAsync({
      project_id: projectId,
      ...value,
    })
    toast.success('Tool created')
    onClose()
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create Tool">
      <ToolDiscoveryForm
        key={open ? 'tools-page-tool-form-open' : 'tools-page-tool-form-closed'}
        submitLabel="Create"
        loading={createTool.isPending}
        testLoading={testTool.isPending}
        onSubmit={handleSubmit}
        onCancel={onClose}
        onTest={(request) => testTool.mutateAsync(request)}
      />
    </Dialog>
  )
}
