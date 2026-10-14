import { AlertTriangle } from 'lucide-react'

export function ApiKeySafetyNotice() {
  return (
    <div className="rounded-lg border border-yellow-500/50 bg-yellow-500/10 p-4">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
        <div>
          <p className="font-mono text-sm font-medium text-warning">Copy this key now</p>
          <p className="text-xs text-warning">It is shown once and cannot be recovered later.</p>
        </div>
      </div>
    </div>
  )
}
