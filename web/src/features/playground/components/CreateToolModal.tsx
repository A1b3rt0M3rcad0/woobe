import { useParams } from 'react-router-dom'
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

function mcpReadinessAction(tool: Tool): string | null {
  const config = (tool.config || {}) as { mcp_readiness?: { action?: string } }
  return config.mcp_readiness?.action || null
}

export function CreateToolModal({ open, onClose, projectId, agentId, onCreated }: CreateToolModalProps) {
  const createTool = useCreateTool()
  const { organizationId } = useParams<{ organizationId: string }>()

  const handleSubmit = async (value: ApiFirstToolFormSubmitValue) => {
    const tool = await createTool.mutateAsync({ project_id: projectId, agent_id: agentId, ...value })
    onCreated(tool)
    onClose()

    if (isMcpTool(tool)) {
      const action = mcpReadinessAction(tool)
      if (action === 'connect') {
        toast.success(`MCP provider "${tool.name}" created. Connect it to load protected tools.`)
      } else {
        toast.success(`MCP provider "${tool.name}" created and loaded for this agent.`)
      }
      return
    }

    toast.success(`Tool "${tool.name}" created for this agent.`)
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create Tool">
      <ApiFirstToolForm
        key={open ? `playground-tool-form-open-${organizationId || 'project'}` : 'playground-tool-form-closed'}
        submitLabel="Create"
        loading={createTool.isPending}
        onSubmit={handleSubmit}
        onCancel={onClose}
      />
    </Dialog>
  )
}
