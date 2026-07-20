import { Dialog } from '@/components/ui/Dialog'
import { ApiFirstToolForm, type ApiFirstToolFormSubmitValue } from '@/features/tools/components/ApiFirstToolForm'
import { useUpdateTool } from '@/features/tools/hooks'
import type { Tool } from '@/features/tools/types'
import { toast } from 'sonner'

interface EditHttpGroupModalProps {
  tool: Tool
  onClose: () => void
  onSaved: () => void
}

export function EditHttpGroupModal({ tool, onClose, onSaved }: EditHttpGroupModalProps) {
  const updateTool = useUpdateTool()

  const handleSubmit = async (value: ApiFirstToolFormSubmitValue) => {
    try {
      await updateTool.mutateAsync({
        toolId: tool.id,
        data: value,
      })
      toast.success(`HTTP API "${value.name}" updated`)
      onSaved()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update HTTP API')
    }
  }

  return (
    <Dialog open onClose={onClose} title={`Edit HTTP API: ${tool.name}`} className="max-h-[calc(100svh-2rem)] max-w-6xl overflow-y-auto bg-surface/95">
      <ApiFirstToolForm
        initialTool={tool}
        submitLabel="Save changes"
        loading={updateTool.isPending}
        onSubmit={handleSubmit}
        onCancel={onClose}
      />
    </Dialog>
  )
}
