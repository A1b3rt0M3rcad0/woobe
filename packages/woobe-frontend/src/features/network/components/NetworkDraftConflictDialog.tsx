import { GitCompareArrows, RefreshCw } from 'lucide-react'
import { Alert, AlertDescription, Button, Dialog } from '@woobe/ui'

export function NetworkDraftConflictDialog({ onClose, onReload }: { onClose: () => void; onReload: () => void }) {
  return (
    <Dialog open onClose={onClose} title="Network Draft changed elsewhere" className="max-w-dialog-compact">
      <div className="space-y-ui-lg">
        <Alert variant="warning">
          <AlertDescription>
            <span className="flex items-start gap-ui-sm">
              <GitCompareArrows className="mt-ui-hairline h-icon w-icon shrink-0" />
              <span>Another request saved a newer revision. Your local composition was not overwritten.</span>
            </span>
          </AlertDescription>
        </Alert>
        <p className="font-sans text-product-small leading-5 text-muted-foreground">
          Reload the current server Draft before making more changes. This intentionally discards the unsaved local composition.
        </p>
        <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-md">
          <Button type="button" variant="outline" onClick={onClose}>Keep local view</Button>
          <Button type="button" onClick={onReload}>
            <RefreshCw className="mr-ui-xs h-icon-sm w-icon-sm" />
            Reload server Draft
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
