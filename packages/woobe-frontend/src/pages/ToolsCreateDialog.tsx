import { Dialog } from '@/components/ui/Dialog'
import { ApiFirstToolForm, type ApiFirstToolFormSubmitValue } from '@/features/tools/components/ApiFirstToolForm'
import { useCreateTool } from '@/features/tools/hooks'
import type { Tool } from '@/features/tools/types'
import { toast } from 'sonner'

interface ToolsCreateDialogProps {
  open: boolean
  projectId: string
  agentId?: string | null
  formKey?: string
  title?: string
  onClose: () => void
  onCreated?: (tool: Tool) => void | Promise<void>
}

export function ToolsCreateDialog({ open, projectId, agentId = null, formKey = 'tools-page-tool-form', title = 'Create Tool', onClose, onCreated }: ToolsCreateDialogProps) {
  const createTool = useCreateTool()

  const handleSubmit = async (value: ApiFirstToolFormSubmitValue) => {
    const tool = await createTool.mutateAsync({ project_id: projectId, agent_id: agentId, ...value })
    await onCreated?.(tool)
    toast.success(value.type === 'http' ? 'HTTP API created' : 'MCP provider created')
    onClose()
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      className="max-w-dialog-wide bg-surface/95"
      contentClassName="p-0 [&>form]:flex [&>form]:min-h-full [&>form]:flex-col [&>form>div:first-child]:flex-1"
      scrollMode="content"
    >
      <ApiFirstToolForm
        key={open ? `${formKey}-open` : `${formKey}-closed`}
        submitLabel="Create"
        loading={createTool.isPending}
        onSubmit={handleSubmit}
        onCancel={onClose}
      />
    </Dialog>
  )
}
