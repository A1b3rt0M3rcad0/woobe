import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Bot, Plus, Puzzle, Upload } from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard, ResourcePill } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { useAgents } from '@/features/agents/hooks'
import { listSkills } from '@/features/skills/api'
import { ManageSkillsDialog } from '@/features/skills/ManageSkillsDialog'
import { savedSkillInstallations } from '@/features/skills/installations'
import type { SkillCatalogMode } from '@/features/skills/SkillCatalog'
import type { SkillSnapshot, SkillSummary } from '@/features/skills/types'
import { workspaceProjectPath } from '@/lib/constants/routes'

type SkillsTab = 'catalog' | 'installed'
interface SkillDialogState {
  title: string
  mode: SkillCatalogMode
  versionId?: string
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Not recorded'
}

function plural(count: number, singular: string, pluralValue = `${singular}s`) {
  return `${count} ${count === 1 ? singular : pluralValue}`
}

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
  const [offset, setOffset] = useState(0)
  const [dialog, setDialog] = useState<SkillDialogState | null>(null)
  const [pending, setPending] = useState<SkillSnapshot | null>(null)
  const [agentQuery, setAgentQuery] = useState('')

  const skills = useQuery({
    queryKey: ['skills', projectId, query.trim(), offset],
    queryFn: () => listSkills(projectId, query.trim(), offset),
    enabled: tab === 'catalog',
  })
  const items = skills.data ?? []
  const installations = useMemo(() => savedSkillInstallations(agents.data ?? [], projectId), [agents.data, projectId])
  const installedAgentCounts = useMemo(() => {
    const agentsBySkill = new Map<string, Set<string>>()
    installations.forEach(({ agent, binding }) => {
      const ids = agentsBySkill.get(binding.skill_id) ?? new Set<string>()
      ids.add(agent.id)
      agentsBySkill.set(binding.skill_id, ids)
    })
    return new Map([...agentsBySkill.entries()].map(([skillId, agentIds]) => [skillId, agentIds.size]))
  }, [installations])
  const normalizedQuery = query.trim().toLowerCase()
  const filteredInstallations = installations.filter(({ agent, binding, snapshot }) => (
    !normalizedQuery
    || `${agent.name} ${snapshot?.package.name ?? binding.skill_id} ${snapshot?.version ?? ''}`.toLowerCase().includes(normalizedQuery)
  ))
  const availableAgents = (agents.data ?? []).filter(agent => agent.project_id === projectId && agent.name.toLowerCase().includes(agentQuery.trim().toLowerCase()))

  const agentPath = (agentId: string, versionId?: string) => {
    const params = new URLSearchParams({ editor: 'skills' })
    if (versionId) params.set('skill_version_id', versionId)
    return `${workspaceProjectPath(workspaceId, projectId, 'agents', agentId, 'playground')}?${params}`
  }
  const openCatalog = (mode: SkillCatalogMode, title: string, versionId?: string) => {
    setDialog({ mode, title, versionId })
  }
  const openSkill = (skill: SkillSummary) => {
    if (!skill.latest_version_id) return
    openCatalog('browse', skill.name, skill.latest_version_id)
  }
  const changeTab = (value: SkillsTab) => {
    setTab(value)
    setQuery('')
    setOffset(0)
  }
  const changeQuery = (value: string) => {
    setQuery(value)
    setOffset(0)
  }

  return <ResourcePage
    title="Skills"
    description="Create, import and version reusable procedures that Agents can load on demand."
    action={<div className="flex flex-wrap justify-end gap-2">
      <Button variant="outline" onClick={() => openCatalog('import', 'Import Skill')}><Upload className="mr-2 h-4 w-4" />Import Skill</Button>
      <Button onClick={() => openCatalog('create', 'Create Skill')}><Plus className="mr-2 h-4 w-4" />Create Skill</Button>
    </div>}
  >
    <ResourceToolbar>
      <ResourceTabs
        label="Skills views"
        value={tab}
        onChange={changeTab}
        tabs={[
          { value: 'catalog', label: 'All Skills' },
          { value: 'installed', label: 'Installed on Agents', count: agents.isSuccess ? installations.length : undefined },
        ]}
      />
      <ResourceSearch
        value={query}
        onChange={changeQuery}
        label={tab === 'catalog' ? 'Search Skills' : 'Search installed Skills'}
        placeholder={tab === 'catalog' ? 'Search Skills by name…' : 'Search by Skill or Agent…'}
      />
    </ResourceToolbar>

    {tab === 'catalog' ? <section aria-label="Project Skills">
      <ResourceSectionHeader
        title="Skills"
        description="Open a Skill to inspect its current version, history, resources and installation options."
        count={offset ? `Page ${offset / 20 + 1}` : items.length < 20 ? items.length : undefined}
      />
      {skills.isPending ? <LoadingState message="Loading Skills" variant="panel" layout="compact-cards" /> : skills.isError ? <ErrorState error={skills.error} onRetry={() => void skills.refetch()} className="rounded-xl border border-border/80 bg-surface/40 py-10" /> : items.length ? <>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map(skill => {
            const installedOn = installedAgentCounts.get(skill.id) ?? 0
            return <ResourceCard
              key={skill.id}
              aria-label={`Open Skill ${skill.name}`}
              onClick={() => openSkill(skill)}
              disabled={!skill.latest_version_id}
              showChevron={Boolean(skill.latest_version_id)}
              icon={<Puzzle className="h-4 w-4" />}
              title={skill.name}
              subtitle={skill.latest_description || 'Reusable Agent procedure'}
              metadata={<>
                <ResourcePill tone="primary">{skill.latest_version ? `v${skill.latest_version}` : 'No version'}</ResourcePill>
                <ResourcePill>{plural(skill.version_count, 'version')}</ResourcePill>
                <ResourcePill tone={installedOn ? 'success' : 'default'}>{installedOn ? plural(installedOn, 'Agent') : 'Not installed'}</ResourcePill>
                {skill.latest_estimated_instruction_units != null && <ResourcePill>≈ {skill.latest_estimated_instruction_units.toLocaleString()} units</ResourcePill>}
                {skill.latest_required_tools.length > 0 && <ResourcePill>{plural(skill.latest_required_tools.length, 'Tool')}</ResourcePill>}
                {skill.latest_resource_count > 0 && <ResourcePill>{plural(skill.latest_resource_count, 'resource')}</ResourcePill>}
              </>}
              footer={`Updated · ${formatDate(skill.latest_version_created_at || skill.created_at)}`}
            />
          })}
        </div>
        {(offset > 0 || items.length >= 20) && <div className="mt-4 flex items-center justify-end gap-2">
          <Button size="sm" variant="ghost" disabled={!offset || skills.isFetching} onClick={() => setOffset(current => Math.max(0, current - 20))}>Previous</Button>
          <span className="text-xs text-muted">Page {offset / 20 + 1}</span>
          <Button size="sm" variant="ghost" disabled={items.length < 20 || skills.isFetching} onClick={() => setOffset(current => current + 20)}>Next</Button>
        </div>}
      </> : <ResourceEmptyState
        icon={<Puzzle className="h-4 w-4" />}
        title={query ? 'No Skills found' : 'No Skills yet'}
        description={query ? 'Try another name or clear the current search.' : 'Create or import the first reusable procedure for this Project.'}
        action={query ? <Button size="sm" variant="outline" onClick={() => changeQuery('')}>Clear search</Button> : <Button size="sm" onClick={() => openCatalog('create', 'Create Skill')}>Create Skill</Button>}
      />}
    </section> : <section aria-label="Installed Skills">
      <ResourceSectionHeader
        title="Installed on Agents"
        description="Saved Agent configurations only. Unsaved edits and historical Releases are not shown."
        count={normalizedQuery ? `${filteredInstallations.length} of ${installations.length}` : installations.length}
      />
      {agents.isPending ? <LoadingState message="Loading installed Skills" variant="panel" layout="compact-cards" /> : agents.isError ? <ErrorState error={agents.error} onRetry={() => void agents.refetch()} className="rounded-xl border border-border/80 bg-surface/40 py-10" /> : filteredInstallations.length ? <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filteredInstallations.map(({ agent, binding, snapshot }) => <ResourceCard
          key={`${agent.id}:${binding.skill_id}`}
          aria-label={`Open Agent Skills for ${agent.name}`}
          onClick={() => navigate(agentPath(agent.id))}
          icon={<Puzzle className="h-4 w-4" />}
          title={snapshot?.package.name ?? binding.skill_id}
          subtitle={agent.name}
          metadata={<>
            <ResourcePill tone="primary">{snapshot?.version ? `v${snapshot.version}` : binding.skill_version_id}</ResourcePill>
            <ResourcePill tone={binding.enabled ? 'success' : 'warning'}>{binding.enabled ? 'Enabled' : 'Disabled'}</ResourcePill>
            <ResourcePill><Bot className="mr-1 inline h-3 w-3" />Agent</ResourcePill>
          </>}
          footer="Open Agent Skills editor"
        />)}
      </div> : <ResourceEmptyState
        icon={<Puzzle className="h-4 w-4" />}
        title={query ? 'No matching installations' : 'No Skills installed on Agents'}
        description={query ? 'Try another Skill or Agent name.' : 'Choose a Skill version, select an Agent and save its draft configuration.'}
        action={<Button variant="outline" size="sm" onClick={() => changeTab('catalog')}>Browse Skills</Button>}
      />}
    </section>}

    {dialog && <ManageSkillsDialog
      key={`${dialog.mode}:${dialog.versionId ?? 'new'}`}
      title={dialog.title}
      projectId={projectId}
      initialMode={dialog.mode}
      initialVersionId={dialog.versionId}
      showCreateActions={false}
      onClose={() => setDialog(null)}
      onInstall={version => { setAgentQuery(''); setPending(version) }}
    />}

    {pending && <Dialog open onClose={() => setPending(null)} title="Choose an Agent" scrollMode="content">
      <div className="space-y-4">
        <p className="text-sm text-muted">Open the Agent’s Skills editor to review <span className="font-medium text-foreground">{pending.package.name} {pending.version}</span> and save the installation in its draft.</p>
        <ResourceSearch label="Search Agents for Skill installation" placeholder="Search Agents…" value={agentQuery} onChange={setAgentQuery} />
        {agents.isPending ? <LoadingState message="Loading Agents" /> : agents.isError ? <ErrorState error={agents.error} onRetry={() => void agents.refetch()} /> : availableAgents.length ? <div className="space-y-2">{availableAgents.map(agent => <Button key={agent.id} variant="outline" className="w-full justify-start" onClick={() => navigate(agentPath(agent.id, pending.skill_version_id))}><Bot className="mr-2 h-4 w-4" />{agent.name}</Button>)}</div> : <p className="text-sm text-muted">{agentQuery ? 'No matching Agents.' : 'Create an Agent before installing this Skill.'}</p>}
      </div>
    </Dialog>}
  </ResourcePage>
}
