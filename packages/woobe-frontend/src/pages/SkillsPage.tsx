import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Bot, Plus, Puzzle, Upload } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceEmptyState, ResourcePage, ResourceSearch, ResourceTabs, ResourceToolbar } from '@/components/common/ResourcePage'
import { useAgents } from '@/features/agents/hooks'
import { SkillCatalog, type SkillCatalogMode } from '@/features/skills/SkillCatalog'
import { savedSkillInstallations } from '@/features/skills/installations'
import type { SkillSnapshot } from '@/features/skills/types'
import { workspaceProjectPath } from '@/lib/constants/routes'

type SkillsTab = 'catalog' | 'installed'

export default function SkillsPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>()
  if (!projectId) return <ErrorState message="Select a Project to manage Skills." />
  return <ProjectSkills key={projectId} workspaceId={workspaceId} projectId={projectId} />
}

function ProjectSkills({ workspaceId, projectId }: { workspaceId?: string; projectId: string }) {
  const navigate = useNavigate()
  const agents = useAgents(projectId)
  const [tab, setTab] = useState<SkillsTab>('catalog')
  const [query, setQuery] = useState('')
  const [catalog, setCatalog] = useState<{ mode: SkillCatalogMode; key: number }>({ mode: 'browse', key: 0 })
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState<SkillSnapshot | null>(null)
  const [agentQuery, setAgentQuery] = useState('')
  const installations = useMemo(() => savedSkillInstallations(agents.data ?? [], projectId), [agents.data, projectId])
  const filtered = installations.filter(({ agent, binding, snapshot }) => `${agent.name} ${snapshot?.package.name ?? binding.skill_id} ${snapshot?.version ?? ''}`.toLowerCase().includes(query.trim().toLowerCase()))
  const availableAgents = (agents.data ?? []).filter(agent => agent.project_id === projectId && agent.name.toLowerCase().includes(agentQuery.trim().toLowerCase()))
  const agentPath = (agentId: string, versionId?: string) => {
    const params = new URLSearchParams({ editor: 'skills' })
    if (versionId) params.set('skill_version_id', versionId)
    return `${workspaceProjectPath(workspaceId, projectId, 'agents', agentId, 'playground')}?${params}`
  }
  const openMode = (mode: SkillCatalogMode) => { setTab('catalog'); setCatalog(current => ({ mode, key: current.key + 1 })) }

  return <ResourcePage title="Skills" description="Create, import and version reusable procedures for your Agents." action={<><Button variant="outline" disabled={busy} onClick={() => openMode('import')}><Upload className="mr-2 h-4 w-4" />Import Skill</Button><Button disabled={busy} onClick={() => openMode('create')}><Plus className="mr-2 h-4 w-4" />Create Skill</Button></>}>
    <ResourceToolbar>
      <ResourceTabs label="Skills views" value={tab} onChange={value => { if (!busy) setTab(value) }} tabs={[{ value: 'catalog', label: 'All Skills' }, { value: 'installed', label: 'Installed on Agents', count: agents.isSuccess ? installations.length : undefined }]} />
      {tab === 'installed' && <ResourceSearch value={query} onChange={setQuery} label="Search installed Skills" placeholder="Search by Skill or Agent…" />}
    </ResourceToolbar>
    {tab === 'catalog' ? <div className="rounded-xl border border-border bg-surface/40 p-5"><SkillCatalog showCreateActions={false} key={catalog.key} projectId={projectId} initialMode={catalog.mode} onBusyChange={setBusy} onInstall={version => { setAgentQuery(''); setPending(version) }} /></div> : <section className="space-y-4" aria-label="Installed Skills">
      <p className="text-xs text-muted">Fixed versions in saved Agent configurations, including disabled bindings. Unsaved edits and historical Releases are not shown.</p>
      {agents.isPending ? <LoadingState message="Loading installed Skills" /> : agents.isError ? <ErrorState error={agents.error} onRetry={() => void agents.refetch()} /> : filtered.length ? <div className="grid gap-3 lg:grid-cols-2">
        {filtered.map(({ agent, binding, snapshot }) => <article key={`${agent.id}:${binding.skill_id}`} className="rounded-xl border border-border bg-surface/50 p-4">
          <div className="flex items-start gap-3"><Puzzle className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" /><div className="min-w-0 flex-1"><h2 className="break-words text-sm font-semibold">{snapshot?.package.name ?? binding.skill_id}</h2><p className="mt-1 text-xs text-muted">{snapshot?.version ?? binding.skill_version_id} · {binding.enabled ? 'Enabled' : 'Disabled'}</p></div></div>
          <p className="mt-3 flex items-center gap-2 text-xs text-muted"><Bot className="h-3.5 w-3.5" />{agent.name}</p>
          <Link className="mt-3 inline-block text-xs font-medium text-primary-light hover:underline" to={agentPath(agent.id)}>Configure Agent Skills</Link>
        </article>)}
      </div> : <ResourceEmptyState icon={<Puzzle className="h-5 w-5" />} title={query ? 'No matching installations' : 'No Skills installed on Agents'} description={query ? 'Try another Skill or Agent name.' : 'Choose a version from the Project catalog, select an Agent and save its draft.'} action={<Button variant="outline" onClick={() => openMode('browse')}>Browse Skills</Button>} />}
    </section>}
    {pending && <Dialog open onClose={() => setPending(null)} title="Choose an Agent" scrollMode="content">
      <div className="space-y-4">
        <p className="text-sm text-muted">Open the Agent’s Skills editor to review <span className="font-medium text-foreground">{pending.package.name} {pending.version}</span> and save the installation in its draft.</p>
        <ResourceSearch label="Search Agents for Skill installation" placeholder="Search Agents…" value={agentQuery} onChange={setAgentQuery} />
        {agents.isPending ? <LoadingState message="Loading Agents" /> : agents.isError ? <ErrorState error={agents.error} onRetry={() => void agents.refetch()} /> : availableAgents.length ? <div className="space-y-2">{availableAgents.map(agent => <Button key={agent.id} variant="outline" className="w-full justify-start" onClick={() => navigate(agentPath(agent.id, pending.skill_version_id))}><Bot className="mr-2 h-4 w-4" />{agent.name}</Button>)}</div> : <p className="text-sm text-muted">{agentQuery ? 'No matching Agents.' : 'Create an Agent before installing this Skill.'} <Link className="text-primary-light hover:underline" to={workspaceProjectPath(workspaceId, projectId, 'agents')}>Open Agents</Link></p>}
      </div>
    </Dialog>}
  </ResourcePage>
}
