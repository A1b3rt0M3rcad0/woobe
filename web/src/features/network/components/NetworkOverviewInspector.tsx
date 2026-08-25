import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Workflow } from 'lucide-react'
import { toast } from 'sonner'

import { useUpdateNetworkMetadata } from '@/features/network/hooks'
import { cn } from '@/lib/utils'

import type { NetworkDefinition } from '../types'
import type { NetworkDefinitionChange } from '../editor/types'
import { NetworkInspectorModal, networkInspectorAction, networkInspectorInput } from './NetworkInspectorModal'

export function NetworkOverviewInspector({
  definition,
  readOnly,
  name,
  description,
  onMetadata: _onMetadata,
  onChange,
}: {
  definition: NetworkDefinition
  readOnly: boolean
  name: string
  description: string
  onMetadata: (metadata: { name?: string; description?: string }) => void
  onChange: (change: NetworkDefinitionChange) => void
}) {
  const { projectId, networkId } = useParams<{ projectId: string; networkId: string }>()
  const metadataMutation = useUpdateNetworkMetadata(projectId, networkId)
  const [identityOpen, setIdentityOpen] = useState(false)
  const [runtimeOpen, setRuntimeOpen] = useState(false)
  const [metadataOverridden, setMetadataOverridden] = useState(false)
  const [displayIdentity, setDisplayIdentity] = useState({ name, description })
  const [identityDraft, setIdentityDraft] = useState({ name, description })
  const [runtimeDraft, setRuntimeDraft] = useState(definition.settings)
  const entryPoint = definition.nodes.find((item) => item.id === definition.root_node_id)?.label ?? 'Not selected'

  useEffect(() => {
    if (metadataOverridden) return
    setDisplayIdentity({ name, description })
    setIdentityDraft({ name, description })
  }, [description, metadataOverridden, name])

  const saveIdentity = async () => {
    const normalizedName = identityDraft.name.trim()
    if (!normalizedName) {
      toast.error('Network name is required')
      return
    }
    try {
      const saved = await metadataMutation.mutateAsync({
        name: normalizedName,
        description: identityDraft.description.trim(),
      })
      const nextIdentity = { name: saved.name, description: saved.description }
      setDisplayIdentity(nextIdentity)
      setIdentityDraft(nextIdentity)
      setMetadataOverridden(true)
      setIdentityOpen(false)
      toast.success('Network metadata updated')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to update Network metadata')
    }
  }

  return (
    <>
      <header className="border-b border-border p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/20 bg-primary/5 text-primary-light"><Workflow className="h-4 w-4" /></div>
          <div className="min-w-0">
            <p className="text-[8px] font-semibold uppercase tracking-widest text-primary-light">Network</p>
            <h2 className="mt-1 truncate text-sm font-semibold text-white">{displayIdentity.name}</h2>
            <p className="mt-1 text-[9px] text-muted">{definition.nodes.length} Agents · {definition.edges.length} delegations</p>
          </div>
        </div>
      </header>

      <div className="space-y-4 p-4">
        {definition.nodes.length === 0 ? (
          <section className="rounded-xl border border-primary/20 bg-primary/5 p-4">
            <p className="text-[10px] font-semibold text-white">Build your Network</p>
            <ol className="mt-3 space-y-2 text-[9px] text-muted">
              <li>1 · Add an Agent</li>
              <li>2 · Choose the Entry Point</li>
              <li>3 · Connect a specialist</li>
            </ol>
          </section>
        ) : null}

        <section className="rounded-xl border border-border bg-background/30 p-3">
          <div className="flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-[9px] font-semibold uppercase tracking-wider text-muted">Network identity</p>
              <p className="mt-1 truncate text-[10px] text-slate-200">{displayIdentity.description.trim() || 'No description yet.'}</p>
            </div>
            <button type="button" onClick={() => { setIdentityDraft(displayIdentity); setIdentityOpen(true) }} className={networkInspectorAction}>{readOnly ? 'View' : 'Edit'}</button>
          </div>
          <p className="mt-2 truncate text-[9px] text-muted">{displayIdentity.name}</p>
        </section>

        <section className="rounded-xl border border-border bg-background/30 p-3">
          <p className="text-[9px] font-semibold uppercase tracking-wider text-muted">Composition</p>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-[9px]">
            <div><dt className="text-muted">Entry point</dt><dd className="mt-1 truncate text-slate-200">{entryPoint}</dd></div>
            <div><dt className="text-muted">Agents</dt><dd className="mt-1 text-slate-200">{definition.nodes.length}</dd></div>
            <div><dt className="text-muted">Delegations</dt><dd className="mt-1 text-slate-200">{definition.edges.length}</dd></div>
            <div><dt className="text-muted">Mode</dt><dd className="mt-1 capitalize text-slate-200">{definition.settings.session_mode}</dd></div>
          </dl>
        </section>

        <section className="rounded-xl border border-border bg-background/30 p-3">
          <div className="flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-[9px] font-semibold uppercase tracking-wider text-muted">Runtime</p>
              <p className="mt-1 truncate text-[10px] text-slate-200">{definition.settings.session_mode} · depth {definition.settings.max_depth} · {definition.settings.max_invocations} invocations · {definition.settings.timeout_seconds}s</p>
            </div>
            <button type="button" onClick={() => { setRuntimeDraft(definition.settings); setRuntimeOpen(true) }} className={networkInspectorAction}>{readOnly ? 'View' : 'Edit'}</button>
          </div>
        </section>
      </div>

      {identityOpen ? (
        <NetworkInspectorModal
          title={readOnly ? 'Network identity' : 'Edit Network identity'}
          description="Name and description document the operational purpose of this Network. Metadata changes do not create a Draft revision."
          onClose={() => setIdentityOpen(false)}
          footer={readOnly ? (
            <button type="button" onClick={() => setIdentityOpen(false)} className={networkInspectorAction}>Close</button>
          ) : (
            <>
              <button type="button" onClick={() => setIdentityOpen(false)} className={networkInspectorAction}>Cancel</button>
              <button type="button" disabled={metadataMutation.isPending} onClick={() => void saveIdentity()} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-50">{metadataMutation.isPending ? 'Saving…' : 'Save'}</button>
            </>
          )}
        >
          <div className="space-y-4">
            <label className="block text-[10px] text-muted">Name<input disabled={readOnly || metadataMutation.isPending} className={networkInspectorInput} value={identityDraft.name} onChange={(event) => setIdentityDraft((current) => ({ ...current, name: event.target.value }))} /></label>
            <label className="block text-[10px] text-muted">Description<textarea disabled={readOnly || metadataMutation.isPending} className={cn(networkInspectorInput, 'min-h-28 resize-y')} value={identityDraft.description} onChange={(event) => setIdentityDraft((current) => ({ ...current, description: event.target.value }))} /></label>
          </div>
        </NetworkInspectorModal>
      ) : null}

      {runtimeOpen ? (
        <NetworkInspectorModal
          title={readOnly ? 'Runtime settings' : 'Edit runtime settings'}
          description="These limits apply to future Network executions."
          onClose={() => setRuntimeOpen(false)}
          footer={readOnly ? (
            <button type="button" onClick={() => setRuntimeOpen(false)} className={networkInspectorAction}>Close</button>
          ) : (
            <>
              <button type="button" onClick={() => setRuntimeOpen(false)} className={networkInspectorAction}>Cancel</button>
              <button type="button" onClick={() => { onChange({ type: 'settings', settings: runtimeDraft }); setRuntimeOpen(false) }} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white">Save</button>
            </>
          )}
        >
          <div className="grid grid-cols-2 gap-4">
            <label className="text-[10px] text-muted">Session mode<select disabled={readOnly} className={networkInspectorInput} value={runtimeDraft.session_mode} onChange={(event) => setRuntimeDraft((current) => ({ ...current, session_mode: event.target.value as 'stateful' | 'stateless' }))}><option value="stateful">Stateful</option><option value="stateless">Stateless</option></select></label>
            <label className="text-[10px] text-muted">Max depth<input disabled={readOnly} type="number" min={1} max={8} className={networkInspectorInput} value={runtimeDraft.max_depth} onChange={(event) => setRuntimeDraft((current) => ({ ...current, max_depth: Number(event.target.value) }))} /></label>
            <label className="text-[10px] text-muted">Max invocations<input disabled={readOnly} type="number" min={1} max={64} className={networkInspectorInput} value={runtimeDraft.max_invocations} onChange={(event) => setRuntimeDraft((current) => ({ ...current, max_invocations: Number(event.target.value) }))} /></label>
            <label className="text-[10px] text-muted">Timeout<input disabled={readOnly} type="number" min={1} max={300} className={networkInspectorInput} value={runtimeDraft.timeout_seconds} onChange={(event) => setRuntimeDraft((current) => ({ ...current, timeout_seconds: Number(event.target.value) }))} /></label>
          </div>
        </NetworkInspectorModal>
      ) : null}
    </>
  )
}
