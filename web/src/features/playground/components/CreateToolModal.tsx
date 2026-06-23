import { useNavigate, useParams } from 'react-router-dom'
import { Dialog } from '@/components/ui/Dialog'
import { ApiFirstToolForm, type ApiFirstToolFormSubmitValue } from '@/features/tools/components/ApiFirstToolForm'
import { useCreateTool } from '@/features/tools/hooks'
import type { Tool } from '@/features/tools/types'
import { toast } from 'sonner'

interface CreateToolModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  onCreated: (tool: Tool) => void
}

function isMcpTool(tool: Tool): boolean {
  const config = (tool.config || {}) as Record<string, unknown>
  return String(tool.type).toLowerCase().includes('mcp') || config.protocol === 'mcp'
}

export function CreateToolModal({ open, onClose, projectId, onCreated }: CreateToolModalProps) {
  const createTool = useCreateTool()
  const navigate = useNavigate()
  const { organizationId } = useParams<{ organizationId: string }>()

  const handleSubmit = async (value: ApiFirstToolFormSubmitValue) => {
    const tool = await createTool.mutateAsync({ project_id: projectId, ...value })
    onCreated(tool)
    onClose()

    if (isMcpTool(tool)) {
      toast.success(`MCP provider "${tool.name}" created. Connect it before enabling tools.`)
      const basePath = organizationId
        ? `/organizations/${organizationId}/projects/${projectId}/tools`
        : `/projects/${projectId}/tools`
      navigate(`${basePath}?configure_mcp_permissions=${tool.id}`)
      return
    }

    toast.success(`Tool "${tool.name}" created. Use Import to add it to this agent.`)
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create Tool">
      <ApiFirstToolForm
        key={open ? 'playground-tool-form-open' : 'playground-tool-form-closed'}
        submitLabel="Create"
        loading={createTool.isPending}
        onSubmit={handleSubmit}
        onCancel={onClose}
      />
    </Dialog>
  )
}
