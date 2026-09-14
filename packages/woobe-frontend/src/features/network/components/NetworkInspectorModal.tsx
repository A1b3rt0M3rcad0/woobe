import type { ReactNode } from 'react'
import { Dialog } from '@woobe/ui'

export const networkInspectorInput = 'mt-ui-xs w-full rounded-control border border-border bg-control px-ui-md py-ui-xs font-sans text-product-small text-accent-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-50'
export const networkInspectorAction = 'shrink-0 rounded-control border border-border bg-background/35 px-ui-sm py-ui-xs font-mono text-system-label font-medium text-muted-foreground transition-colors hover:border-primary/30 hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-45'

export function NetworkInspectorModal({ title, description, children, footer, onClose }: {
  title: string
  description?: string
  children: ReactNode
  footer: ReactNode
  onClose: () => void
}) {
  return (
    <Dialog open onClose={onClose} title={title} className="max-w-dialog-compact">
      <div className="space-y-ui-md">
        {description ? <p className="font-sans text-product-caption text-muted-foreground">{description}</p> : null}
        <div>{children}</div>
        <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-md">{footer}</div>
      </div>
    </Dialog>
  )
}
