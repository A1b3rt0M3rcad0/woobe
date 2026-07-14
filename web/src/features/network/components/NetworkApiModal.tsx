import { useMemo, useState } from 'react'
import { Copy, KeyRound, Loader2, X } from 'lucide-react'
import { toast } from 'sonner'

import { ScrollArea } from '@/components/ui/ScrollArea'
import { createRuntimeApiKey } from '@/features/api-keys/api'
import { API_BASE_URL } from '@/lib/api/client'
import { cn } from '@/lib/utils'
import type { AgentNodeId, NetworkBinding } from './networkWorkspaceTypes'

const surface = 'rounded-xl border border-border/75 bg-background/35'

type Props = {
  open: boolean
  onClose: () => void
  projectId: string
  networkId: string
  versionIds: { staging?: string | null; production?: string | null }
  bindings: {
    staging: Record<AgentNodeId, NetworkBinding>
    production: Record<AgentNodeId, NetworkBinding>
  }
}

export function NetworkApiModal({
  open,
  onClose,
  projectId,
  networkId,
  versionIds,
  bindings,
}: Props) {
  const [environment, setEnvironment] = useState<'staging' | 'production'>('staging')
  const [creating, setCreating] = useState(false)
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const active = bindings[environment]
  const versionId = versionIds[environment]
  const curl = useMemo(() => `curl -X POST "${API_BASE_URL}/v1/run" \\
  -H "Authorization: Bearer $WOOBE_API_KEY" \\
  -H "Content-Type: application/json" \\
  -H "Idempotency-Key: $(uuidgen)" \\
  -d '{"message":"Hello!"}'`, [])

  if (!open) return null

  const createKey = async () => {
    setCreating(true)
    try {
      const result = await createRuntimeApiKey(projectId, {
        name: `${environment} Network Runtime`,
        target_type: 'network',
        target_id: networkId,
        environment,
        interfaces: ['http', 'stream', 'jobs'],
      })
      setCreatedKey(result.key)
      toast.success('Network Runtime Key created')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to create Runtime Key')
    } finally {
      setCreating(false)
    }
  }

  const copy = (value: string) => {
    void navigator.clipboard?.writeText(value)
    toast.success('Copied')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur">
      <div className="flex h-[82vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border bg-surface">
        <div className="flex shrink-0 items-start border-b border-border p-5">
          <div>
            <p className="text-[9px] uppercase tracking-widest text-primary-light">Network runtime</p>
            <h2 className="mt-1 text-base font-semibold text-white">API Reference</h2>
            <p className="mt-1 text-[10px] text-muted">Native Runtime API is available only for Staging and Production.</p>
          </div>
          <button onClick={onClose} className="ml-auto text-muted"><X className="h-4 w-4" /></button>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-[320px_1fr]">
          <ScrollArea className="border-r border-border">
            <div className="p-4">
              <p className="text-[9px] uppercase text-muted">Environment</p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {(['staging', 'production'] as const).map((item) => (
                  <button
                    key={item}
                    onClick={() => { setEnvironment(item); setCreatedKey(null) }}
                    className={cn('rounded-xl border p-3 text-left', item === environment ? 'border-primary/35 bg-primary/10' : 'border-border bg-background/35')}
                  >
                    <p className="text-[10px] font-semibold capitalize text-white">{item}</p>
                    <p className="mt-1 font-mono text-[9px] text-muted">{versionIds[item] ? 'ready' : 'not promoted'}</p>
                  </button>
                ))}
              </div>

              <div className={cn(surface, 'mt-4 p-3')}>
                <p className="text-[9px] uppercase text-muted">Pinned Network version</p>
                <p className="mt-1 break-all font-mono text-[10px] text-white">{versionId ?? 'Promote this environment first'}</p>
              </div>

              <p className="mt-4 text-[9px] uppercase text-muted">Composition</p>
              <div className="mt-2 space-y-2">
                {Object.values(active).map((item) => (
                  <div key={item.nodeId} className={cn(surface, 'flex justify-between p-2.5')}>
                    <span className="truncate text-[9px] text-white">{item.agent.name}</span>
                    <span className="font-mono text-[8px] text-emerald-300">{item.version}</span>
                  </div>
                ))}
              </div>

              <div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-3">
                <div className="flex gap-2">
                  <KeyRound className="h-4 w-4 text-primary-light" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[10px] text-white">{environment} Network Key</p>
                    <p className="truncate font-mono text-[9px] text-muted">{createdKey ?? 'Not generated in this view'}</p>
                  </div>
                  {createdKey ? <button onClick={() => copy(createdKey)} className="text-muted"><Copy className="h-3.5 w-3.5" /></button> : null}
                </div>
                <p className="mt-2 text-[9px] text-muted">target_type=network · target_id={networkId}</p>
                <button
                  type="button"
                  disabled={creating || !versionId}
                  onClick={() => void createKey()}
                  className="mt-3 flex w-full items-center justify-center rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {creating ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <KeyRound className="mr-1.5 h-3.5 w-3.5" />}
                  Generate one-time key
                </button>
                {createdKey ? <p className="mt-2 text-[9px] text-amber-200">Copy it now. The secret is not shown again.</p> : null}
              </div>
            </div>
          </ScrollArea>

          <ScrollArea>
            <section className="p-5">
              <div className={cn(surface, 'flex items-center gap-2 p-3')}>
                <span className="text-[10px] font-semibold text-primary-light">POST</span>
                <code className="text-[10px] text-white">/v1/run</code>
                <button onClick={() => copy('/v1/run')} className="ml-auto text-muted"><Copy className="h-3.5 w-3.5" /></button>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-4">
                <pre className="rounded-xl border border-border bg-black/20 p-4 text-[10px] text-slate-300">{JSON.stringify({ message: 'Hello!', session_id: '<optional-uuid>' }, null, 2)}</pre>
                <pre className="rounded-xl border border-border bg-black/20 p-4 text-[10px] text-slate-300">{JSON.stringify({ success: true, data: { answer: 'How can I help?', session_id: '<uuid>', execution_id: '<uuid>', network_version_id: versionId ?? '<uuid>', trace_id: '<uuid>' } }, null, 2)}</pre>
              </div>
              <pre className="mt-4 overflow-x-auto rounded-xl border border-border bg-black/20 p-4 text-[10px] text-slate-300">{curl}</pre>
              <div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-4 text-[10px] leading-4 text-muted">
                Use <code>/v1/run/stream</code> for SSE with heartbeat and resumable event IDs, or <code>/v1/jobs</code> for asynchronous execution. Draft remains internal to Network Chat.
              </div>
            </section>
          </ScrollArea>
        </div>
      </div>
    </div>
  )
}
