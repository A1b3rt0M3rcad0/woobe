import { useState } from 'react'
import { Dialog } from '@woobe/ui'
import { SkillCatalog, type SkillCatalogProps } from './SkillCatalog'

export function ManageSkillsDialog({ onClose, title = 'Manage Skills', ...props }: SkillCatalogProps & { onClose: () => void; title?: string }) {
  const [busy, setBusy] = useState(false)

  return (
    <Dialog
      open
      onClose={busy ? () => undefined : onClose}
      title={title}
      className="flex max-h-dialog max-w-dialog-wide flex-col overflow-hidden"
      contentClassName="min-h-0 flex-1 p-0"
    >
      <div className="scrollbar-thin h-full min-h-0 overflow-y-auto p-ui-lg">
        <SkillCatalog
          {...props}
          onBusyChange={setBusy}
          onInstall={props.onInstall ? version => { props.onInstall?.(version); onClose() } : undefined}
        />
      </div>
    </Dialog>
  )
}
