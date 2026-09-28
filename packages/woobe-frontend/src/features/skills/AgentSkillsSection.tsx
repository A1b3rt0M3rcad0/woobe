import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Puzzle, Trash2 } from 'lucide-react'
import { Checkbox, EmptyStatePanel, PanelHeader } from '@woobe/ui'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useContextManagers } from '@/features/agents/hooks'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { workspaceProjectPath } from '@/lib/constants/routes'
import { enableSkillsContext, installSkill, record, skillsConfig } from './config'
import { ManageSkillsDialog } from './ManageSkillsDialog'

function SkillBudgetInput({ value, min, max, onCommit }: { value: number; min: number; max: number; onCommit: (value: number) => void }) {
  const [draft, setDraft] = useState(String(value))
  useEffect(() => { setDraft(String(value)) }, [value])

  const commit = () => {
    const parsed = Number(draft)
    if (Number.isInteger(parsed) && parsed >= min && parsed <= max) onCommit(parsed)
    else setDraft(String(value))
  }

  return <Input type="number" min={min} max={max} step={1} value={draft} onChange={event => setDraft(event.target.value)} onBlur={commit} onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur() }} className="mt-ui-xs [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none" />
}

export function AgentSkillsSection({ projectId }: { projectId: string }) {
  const { state, setField } = useAgentEditor()
  const { data: managers = [], isPending, isError, refetch } = useContextManagers()
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const [params] = useSearchParams()
  const initialVersionId = params.get('skill_version_id') ?? undefined
  const [open, setOpen] = useState(Boolean(initialVersionId))
  const config = skillsConfig(state.runtimeConfig)
  const selection = record(state.runtimeConfig.context_manager ?? state.runtimeConfig.context_assembler)
  const manager = managers.find(item => item.supports_skills && item.name === selection.name) ?? managers.find(item => item.supports_skills && item.is_default) ?? managers.find(item => item.supports_skills)
  const enabled = config.bindings.filter(item => item.enabled).length
  const context = record(state.runtimeConfig.context)
  const policy = record(context.skills)
  const updateBudget = (key: string, value: number) => setField('runtimeConfig', { ...state.runtimeConfig, context: { ...context, skills: { ...policy, [key]: value } } })

  return <>
    <section className="rounded-container border border-border bg-surface/[0.72]" aria-label="Installed Skills">
      <PanelHeader icon={<Puzzle className="h-3.5 w-3.5" />} title="Skills" description={config.bindings.length ? `${config.bindings.length} installed · ${enabled} enabled` : 'Procedures available when needed'} />
      <div className="space-y-ui-md p-ui-md">
        <p className="font-sans text-product-caption text-muted-foreground">The Agent discovers installed Skills and loads their instructions when needed. Loaded content stays available for the current Run.</p>
        {config.bindings.length ? <div className="divide-y divide-border/60 rounded-container border border-border bg-background/20">{config.bindings.map(binding => {
          const snapshot = config.snapshots.find(item => item.skill_version_id === binding.skill_version_id)
          const name = snapshot?.package.name ?? binding.skill_id
          return <div key={binding.skill_id} className="p-ui-md">
            <div className="flex items-start gap-ui-sm">
              <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-ui-sm">
                <Checkbox checked={binding.enabled} disabled={!binding.enabled && !manager} className="mt-ui-xs" onChange={event => {
                  const nextEnabled = event.target.checked
                  const runtime = nextEnabled && manager ? enableSkillsContext(state.runtimeConfig, manager) : state.runtimeConfig
                  setField('runtimeConfig', { ...runtime, skills: { ...config, bindings: config.bindings.map(item => item.skill_id === binding.skill_id ? { ...item, enabled: nextEnabled } : item) } })
                }} aria-label={`Enable ${name}`} />
                <span className="min-w-0"><span className="block break-words font-mono text-system-label font-semibold text-slate-100">{name}</span><span className="mt-ui-xs block font-mono text-system-meta text-muted-foreground">{snapshot?.version ?? 'Pinned version'} · {binding.enabled ? 'Available' : 'Disabled'}</span></span>
              </label>
              <button type="button" aria-label={`Uninstall ${name} from draft`} className="flex h-control-segment w-control-segment shrink-0 items-center justify-center rounded-control border border-transparent text-muted-foreground hover:border-red-500/25 hover:bg-red-500/[0.06] hover:text-red-300" onClick={() => setField('runtimeConfig', { ...state.runtimeConfig, skills: { bindings: config.bindings.filter(item => item.skill_id !== binding.skill_id), snapshots: config.snapshots.filter(item => item.skill_id !== binding.skill_id) } })}><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
            {snapshot?.package.description ? <p className="mt-ui-sm line-clamp-2 font-sans text-product-caption text-muted-foreground">{snapshot.package.description}</p> : null}
          </div>
        })}</div> : <EmptyStatePanel compact title="No Skills installed" description="Install a Skill to make its procedure available to this Agent Draft." />}
        <Button className="w-full" size="sm" variant="outline" disabled={!projectId} onClick={() => setOpen(true)}>Manage Skills</Button>
        {!manager ? <p role={isError ? 'alert' : 'status'} className="font-sans text-product-caption text-muted-foreground">{isPending ? 'Loading compatible Context Managers…' : isError ? 'Unable to load compatible Context Managers.' : 'No installed Context Manager supports Skills.'}</p> : null}
        {isError ? <Button size="sm" variant="ghost" onClick={() => void refetch()}>Retry Context Managers</Button> : null}
        <Link to={workspaceProjectPath(workspaceId, projectId, 'skills')} className="block text-center font-mono text-system-meta text-primary-light hover:underline">Open Project Skills</Link>
        {!!config.bindings.length ? <details className="font-sans text-product-caption text-muted-foreground">
          <summary className="cursor-pointer font-mono text-system-meta text-slate-300">Context budget</summary>
          <div className="mt-ui-md space-y-ui-md border-t border-border/60 pt-ui-md">
            <p>Estimated input units, including the catalog. Instructions are preserved in full. If the budget is exhausted, another activation is declined.</p>
            <label className="block font-mono text-system-meta">Total Skills budget<SkillBudgetInput min={256} max={1000000} value={Number(policy.max_units ?? 8000)} onCommit={value => updateBudget('max_units', value)} /></label>
            <label className="block font-mono text-system-meta">Catalog and search budget<SkillBudgetInput min={128} max={100000} value={Number(policy.catalog_max_units ?? 2000)} onCommit={value => updateBudget('catalog_max_units', value)} /></label>
          </div>
        </details> : null}
      </div>
    </section>
    {open ? <ManageSkillsDialog projectId={projectId} bindings={config.bindings} managerName={manager?.display_name} initialVersionId={initialVersionId} installDisabled={!manager} onClose={() => setOpen(false)} onInstall={snapshot => { if (manager) setField('runtimeConfig', installSkill(state.runtimeConfig, snapshot, manager)) }} /> : null}
  </>
}
