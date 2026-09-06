import { useState } from 'react'
import { ChevronDown, Puzzle, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useContextAssemblers } from '@/features/agents/hooks'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { enableSkillsContext, installSkill, record, skillsConfig } from './config'
import { ManageSkillsDialog } from './ManageSkillsDialog'

export function AgentSkillsSection({ projectId }: { projectId: string }) {
  const { state, setField } = useAgentEditor()
  const { data: managers = [], isPending, isError } = useContextAssemblers()
  const [open, setOpen] = useState(false)
  const config = skillsConfig(state.runtimeConfig)
  const selection = record(state.runtimeConfig.context_assembler)
  const manager = managers.find(item => item.supports_skills && item.name === selection.name && item.version === selection.version)
    ?? managers.find(item => item.supports_skills && !item.is_system_default_alias)
  const enabled = config.bindings.filter(item => item.enabled).length
  const context = record(state.runtimeConfig.context)
  const policy = record(context.skills)
  const updateBudget = (key: string, value: number) => setField('runtimeConfig', { ...state.runtimeConfig, context: { ...context, skills: { ...policy, [key]: value } } })

  return <>
    <details className="group rounded-xl border border-border bg-surface">
      <summary className="flex cursor-pointer list-none items-center gap-3 p-4 [&::-webkit-details-marker]:hidden">
        <Puzzle className="h-4 w-4 shrink-0 text-primary" />
        <span className="min-w-0 flex-1"><span className="block text-sm font-semibold">Skills</span><span className="mt-0.5 block text-[11px] text-muted">{config.bindings.length ? `${config.bindings.length} installed · ${enabled} enabled` : 'Procedures available when needed'}</span></span>
        <ChevronDown className="h-4 w-4 text-muted transition-transform group-open:rotate-180" />
      </summary>
      <div className="space-y-4 border-t border-border p-4">
        <p className="text-xs leading-5 text-muted">The Agent discovers installed Skills and loads their instructions when needed. Loaded content stays available for the current Run.</p>
        {config.bindings.map(binding => {
          const snapshot = config.snapshots.find(item => item.skill_version_id === binding.skill_version_id)
          const name = snapshot?.package.name ?? binding.skill_id
          return <div key={binding.skill_id} className="rounded-lg border border-border p-3">
            <div className="flex items-start gap-2">
              <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-2">
                <input type="checkbox" checked={binding.enabled} disabled={!binding.enabled && !manager} className="mt-0.5 accent-primary" onChange={event => {
                  const enabled = event.target.checked
                  const runtime = enabled && manager ? enableSkillsContext(state.runtimeConfig, manager) : state.runtimeConfig
                  setField('runtimeConfig', { ...runtime, skills: { ...config, bindings: config.bindings.map(item => item.skill_id === binding.skill_id ? { ...item, enabled } : item) } })
                }} aria-label={`Enable ${name}`} />
                <span className="min-w-0"><span className="block break-words text-xs font-medium">{name}</span><span className="block text-[10px] text-muted">{snapshot?.version ?? 'Pinned version'} · {binding.enabled ? 'Available' : 'Disabled'}</span></span>
              </label>
              <button type="button" aria-label={`Uninstall ${name} from draft`} className="rounded p-1 text-muted hover:bg-accent hover:text-red-400" onClick={() => setField('runtimeConfig', { ...state.runtimeConfig, skills: { bindings: config.bindings.filter(item => item.skill_id !== binding.skill_id), snapshots: config.snapshots.filter(item => item.skill_id !== binding.skill_id) } })}><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
            {snapshot?.package.description && <p className="mt-2 line-clamp-2 text-[11px] leading-4 text-muted">{snapshot.package.description}</p>}
          </div>
        })}
        <Button className="w-full" size="sm" variant="outline" disabled={!manager || !projectId} onClick={() => setOpen(true)}>Manage Skills</Button>
        {!manager && <p role={isError ? 'alert' : 'status'} className="text-xs text-muted">{isPending ? 'Loading compatible Context Managers…' : isError ? 'Unable to load Context Managers. Reopen the editor to retry.' : 'No installed Context Manager supports Skills.'}</p>}
        {!!config.bindings.length && <details className="text-xs text-muted">
          <summary className="cursor-pointer">Context budget</summary>
          <div className="mt-3 space-y-3">
            <p className="leading-5">Estimated input units, including the catalog. Instructions are preserved in full. If the budget is exhausted, another activation is declined.</p>
            <label className="block">Total Skills budget<Input type="number" min={256} max={1000000} step={1} value={Number(policy.max_units ?? 8000)} onChange={event => { const value = event.target.valueAsNumber; if (Number.isInteger(value) && value >= 256 && value <= 1000000) updateBudget('max_units', value) }} className="mt-1" /></label>
            <label className="block">Catalog and search budget<Input type="number" min={128} max={100000} step={1} value={Number(policy.catalog_max_units ?? 2000)} onChange={event => { const value = event.target.valueAsNumber; if (Number.isInteger(value) && value >= 128 && value <= 100000) updateBudget('catalog_max_units', value) }} className="mt-1" /></label>
          </div>
        </details>}
      </div>
    </details>
    {open && manager && <ManageSkillsDialog projectId={projectId} bindings={config.bindings} managerName={manager.display_name} onClose={() => setOpen(false)} onInstall={snapshot => setField('runtimeConfig', installSkill(state.runtimeConfig, snapshot, manager))} />}
  </>
}
