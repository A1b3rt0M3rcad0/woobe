import { AlertTriangle, KeyRound } from 'lucide-react'
import { CopyButton } from '@/components/common/CopyButton'
import type { CreateApiKeyResponse } from '@/features/api-keys/types'

interface ApiKeySecretRevealProps {
  apiKey: CreateApiKeyResponse
  agentName?: string | null
}

function permissionLabel(scope: string): string {
  if (scope === 'traces:read') return 'Traces'
  if (scope === 'usage:read') return 'Usage & cost'
  if (scope === 'runtime:execute') return 'Legacy runtime access'
  return scope
}

export function ApiKeySecretReveal({ apiKey, agentName }: ApiKeySecretRevealProps) {
  const runtime = apiKey.kind === 'runtime'

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-yellow-500/35 bg-yellow-500/8 p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-300" />
          <div>
            <p className="text-sm font-semibold text-white">Copy this secret now</p>
            <p className="mt-1 text-xs leading-5 text-muted">It is shown once and cannot be recovered later.</p>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <KeyRound className="h-4 w-4 text-primary-light" />
          {runtime ? 'Runtime Key' : 'Project Key'} created
        </div>
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-border/80 bg-background/80 p-3">
          <code className="min-w-0 flex-1 break-all text-xs text-white">{apiKey.key}</code>
          <CopyButton text={apiKey.key} />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {runtime ? (
          <>
            <div className="rounded-xl border border-border/80 bg-background/50 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Agent</p>
              <p className="mt-1 truncate text-sm font-medium text-white">{agentName || apiKey.agent_id || 'Unknown agent'}</p>
            </div>
            <div className="rounded-xl border border-border/80 bg-background/50 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Environment</p>
              <p className="mt-1 text-sm font-medium capitalize text-white">{apiKey.environment}</p>
            </div>
            <div className="rounded-xl border border-border/80 bg-background/50 p-3 sm:col-span-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Interfaces</p>
              <p className="mt-1 text-sm text-white">{apiKey.interfaces.join(' · ')}</p>
            </div>
          </>
        ) : (
          <div className="rounded-xl border border-border/80 bg-background/50 p-3 sm:col-span-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Permissions</p>
            <p className="mt-1 text-sm text-white">{apiKey.scopes.map(permissionLabel).join(' · ')}</p>
          </div>
        )}
      </div>

      <div>
        <p className="text-xs font-medium text-muted">Environment setup</p>
        <div className="mt-2 flex items-center gap-2 rounded-lg border border-border/80 bg-background/60 p-3">
          <code className="min-w-0 flex-1 break-all text-xs text-muted">export WOOBE_API_KEY=&quot;{apiKey.key}&quot;</code>
          <CopyButton text={`export WOOBE_API_KEY="${apiKey.key}"`} />
        </div>
      </div>
    </div>
  )
}
