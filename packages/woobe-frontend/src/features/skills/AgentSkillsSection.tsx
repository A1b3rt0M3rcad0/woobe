import { Link, useParams, useSearchParams } from 'react-router-dom'
import { workspaceProjectPath } from '@/lib/constants/routes'
import { useEffect, useState } from 'react'
import { Puzzle, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useContextAssemblers } from '@/features/agents/hooks'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { enableSkillsContext, installSkill, record, skillsConfig } from './config'
import { ManageSkillsDialog } from './ManageSkillsDialog'

function StandaloneBudgetInput({
  value,
  min,
  max,
  onCommit,
}: {
  value: number
  min: number
  max: number
  onCommit: (value: number) => void
}) {
  const [draft, setDraft] = useState(String(value))
  useEffect(() => { setDraft(String(value)) }, [value])

  const commit = () => {
    const parsed = Number(draft)
    if (Number.isInteger(parsed) && parsed >= min && parsed <= max) onCommit(parsed)
    else setDraft(String(value))
  }

  return (
    <Input
      type="number"
      min={min}
      max={max}
      step={1}
      value={draft}
      onChange={event => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur() }}
      className="mt-1 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
    />
  )
}

export function AgentSkillsSection({ projectId, standalone = false }: { projectId: string; standalone?: boolean }) {
  const { state, setField } = useAgentEditor()
  const { data: managers = [], isPending, isError, refetch } = useContextAssemblers()
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const [params] = useSearchParams()
  const initialVersionId = params.get('skill_version_id') ?? undefined
  const [open, setOpen] = useState(Boolean(initialVersionId))
  const config = skillsConfig(state.runtimeConfig)
  const selection = record(state.runtimeConfig.context_assembler)
  const manager = managers.find(item => item.supports_skills && item.name === selection.name && item.version === selection.version)
    ?? managers.find(item => item.supports_skills && !item.is_system_default_alias)
  const enabled = config.bindings.filter(item => item.enabled).length
  const context = record(state.runtimeConfig.context)
  const policy = record(context.skills)
  const updateBudget = (key: string, value: number) => setField('runtimeConfig', { ...state.runtimeConfig, context: { ...context, skills: { ...policy, [key]: value } } })

  const body = (
    <>
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
            <button type="button" aria-label={`Uninstall ${name} from draft`} className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-muted hover:bg-accent hover:text-red-400" onClick={() => setField('runtimeConfig', { ...state.runtimeConfig, skills: { bindings: config.bindings.filter(item => item.skill_id !== binding.skill_id), snapshots: config.snapshots.filter(item => item.skill_id !== binding.skill_id) } })}><Trash2 className="h-3.5 w-3.5" /></button>
          </div>
          {snapshot?.package.description && <p className="mt-2 line-clamp-2 text-[11px] leading-4 text-muted">{snapshot.package.description}</p>}
        </div>
      })}
      <Button className="w-full" size="sm" variant="outline" disabled={!projectId} onClick={() => setOpen(true)}>Manage Skills</Button>
      {!manager && <p role={isError ? 'alert' : 'status'} className="text-xs text-muted">{isPending ? 'Loading compatible Context Managers…' : isError ? 'Unable to load compatible Context Managers.' : 'No installed Context Manager supports Skills.'}</p>}
      {isError && <Button size="sm" variant="ghost" onClick={() => void refetch()}>Retry Context Managers</Button>}
      <Link to={workspaceProjectPath(workspaceId, projectId, 'skills')} className="block text-center text-xs text-primary-light hover:underline">Open Project Skills</Link>
      {!!config.bindings.length && <details className="text-xs text-muted">
        <summary className="cursor-pointer">Context budget</summary>
        <div className="mt-3 space-y-3">
          <p className="leading-5">Estimated input units, including the catalog. Instructions are preserved in full. If the budget is exhausted, another activation is declined.</p>
          {standalone ? (
            <>
              <label className="block">Total Skills budget<StandaloneBudgetInput min={256} max={1000000} value={Number(policy.max_units ?? 8000)} onCommit={value => updateBudget('max_units', value)} /></label>
              <label className="block">Catalog and search budget<StandaloneBudgetInput min={128} max={100000} value={Number(policy.catalog_max_units ?? 2000)} onCommit={value => updateBudget('catalog_max_units', value)} /></label>
            </>
          ) : (
            <>
              <label className="block">Total Skills budget<Input type="number" min={256} max={1000000} step={1} value={Number(policy.max_units ?? 8000)} onChange={event => { const value = event.target.valueAsNumber; if (Number.isInteger(value) && value >= 256 && value <= 1000000) updateBudget('max_units', value) }} className="mt-1" /></label>
              <label className="block">Catalog and search budget<Input type="number" min={128} max={100000} step={1} value={Number(policy.catalog_max_units ?? 2000)} onChange={event => { const value = event.target.valueAsNumber; if (Number.isInteger(value) && value >= 128 && value <= 100000) updateBudget('catalog_max_units', value) }} className="mt-1" /></label>
            </>
          )}
        </div>
      </details>}
    </>
  )

  return <>
    {standalone ? (
      <section className="space-y-4 p-4" aria-label="Installed Skills">
        <div>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-white">Skills</p>
              <p className="mt-1 text-[11px] leading-4 text-muted">Versioned procedures available to this Agent and materialized only when requested by the runtime.</p>
            </div>
            <span className="shrink-0 font-mono text-[9px] text-muted">{config.bindings.length} installed · {enabled} enabled</span>
          </div>
        </div>
        {body}
      </section>
    ) : (
      <section className="rounded-xl border border-border bg-surface" aria-label="Installed Skills">
        <div className="flex items-center gap-3 p-4">
          <Puzzle className="h-4 w-4 shrink-0 text-primary" />
          <span className="min-w-0 flex-1"><span className="block text-sm font-semibold">Skills</span><span className="mt-0.5 block text-[11px] text-muted">{config.bindings.length ? `${config.bindings.length} installed · ${enabled} enabled` : 'Procedures available when needed'}</span></span>
        </div>
        <div className="space-y-4 border-t border-border p-4">{body}</div>
      </section>
    )}
    {open && <ManageSkillsDialog projectId={projectId} bindings={config.bindings} managerName={manager?.display_name} initialVersionId={initialVersionId} installDisabled={!manager} onClose={() => setOpen(false)} onInstall={snapshot => { if (manager) setField('runtimeConfig', installSkill(state.runtimeConfig, snapshot, manager)) }} />}
  </>
}
