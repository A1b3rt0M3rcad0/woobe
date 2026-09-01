import { ToolSettingsModal } from '@/features/tools/components/ToolSettingsModal'
import type { Tool } from '@/features/tools/types'

interface EditToolModalProps {
  tool: Tool | null
  onClose: () => void
  onSaved: () => void | Promise<void>
}

export function EditToolModal({ tool, onClose, onSaved }: EditToolModalProps) {
  return (
    <ToolSettingsModal
      tool={tool}
      onClose={onClose}
      onSaved={onSaved}
    />
  )
}
