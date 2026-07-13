import { FileJson2 } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'

interface NetworkOutputHelpModalProps {
  open: boolean
  onClose: () => void
}

export function NetworkOutputHelpModal({ open, onClose }: NetworkOutputHelpModalProps) {
  return (
    <Dialog open={open} onClose={onClose} title="Output contract" className="max-w-2xl overflow-hidden bg-surface/95">
      <div className="space-y-5">
        <div className="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/[0.045] p-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light">
            <FileJson2 className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-medium text-white">Define the shape of the Agent response</p>
            <p className="mt-1 text-xs leading-5 text-muted">
              When JSON output is enabled, the runtime validates the final response against this contract. The same contract is used by Chat and preserved in Agent Releases.
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <section className="rounded-xl border border-border/80 bg-background/55 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted">Type declarations</p>
            <pre className="mt-3 overflow-auto rounded-lg border border-border/70 bg-black/15 p-3 text-[11px] leading-5 text-slate-300">{`{
  "message": "string",
  "confidence": "float",
  "approved": "boolean"
}`}</pre>
            <p className="mt-3 text-xs leading-5 text-muted">
              Values such as <code>"string"</code>, <code>"number"</code>, <code>"float"</code> and <code>"boolean"</code> describe expected types.
            </p>
          </section>

          <section className="rounded-xl border border-border/80 bg-background/55 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted">Nested structures</p>
            <pre className="mt-3 overflow-auto rounded-lg border border-border/70 bg-black/15 p-3 text-[11px] leading-5 text-slate-300">{`{
  "customer": {
    "id": "string",
    "tags": ["string"]
  },
  "items": [{
    "name": "string",
    "quantity": "integer"
  }]
}`}</pre>
            <p className="mt-3 text-xs leading-5 text-muted">
              Objects and arrays can be nested. Keep the contract focused on fields the application actually consumes.
            </p>
          </section>
        </div>

        <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.045] p-4 text-xs leading-5 text-amber-100/90">
          Invalid JSON blocks Draft saving. A valid contract can still fail at runtime when the model response does not match the expected shape; that failure appears in Chat and Traces.
        </div>

        <div className="flex justify-end">
          <Button type="button" onClick={onClose}>Close</Button>
        </div>
      </div>
    </Dialog>
  )
}
