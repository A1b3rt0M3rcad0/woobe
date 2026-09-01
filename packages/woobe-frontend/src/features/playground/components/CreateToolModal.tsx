import { ToolsCreateDialog } from '@/pages/ToolsCreateDialog'
import type { Tool } from '@/features/tools/types'

interface CreateToolModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  onCreated: (tool: Tool) => void
}

export function CreateToolModal({ open, onClose, projectId, agentId, onCreated }: CreateToolModalProps) {
  return (
    <ToolsCreateDialog
      open={open}
      projectId={projectId}
      agentId={agentId}
      formKey="playground-tool-form"
      onClose={onClose}
      onCreated={onCreated}
    />
  )
}
