import { Dialog } from '@/components/ui/Dialog'
import { ToolForm, type ToolFormSubmitValue } from '@/features/tools/components/ToolForm'
import { useCreateTool, useTestTool } from '@/features/tools/hooks'
import type { Tool } from '@/features/tools/types'
import { toast } from 'sonner'

interface CreateToolModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  onCreated: (tool: Tool) => void
}

export function CreateToolModal({ open, onClose, projectId, onCreated }: CreateToolModalProps) {
  const createTool = useCreateTool()
  const testTool = useTestTool()

  const handleSubmit = async (value: ToolFormSubmitValue) => {
    const tool = await createTool.mutateAsync({
      project_id: projectId,
      ...value,
    })
    onCreated(tool)
    onClose()
    toast.success(`Tool "${tool.name}" created. Use Import to add it to this agent.`)
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create Tool">
      <ToolForm
        key={open ? 'playground-tool-form-open' : 'playground-tool-form-closed'}
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
