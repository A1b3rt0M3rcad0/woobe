import { Edit3, Rocket, Save, RotateCcw, Lock } from 'lucide-react'
import { AgentEditorNavigation, useAgentEditorSection } from '@/features/agents/components/AgentEditorNavigation'
import { AgentOverviewSettings } from '@/features/agents/components/AgentOverviewSettings'
import { AgentSkillsSection } from '@/features/skills/AgentSkillsSection'
import { InspectorTabs } from './InspectorTabs'
import { AgentBehaviorSettings } from '@/features/agents/components/AgentBehaviorSettings'
import { AgentRuntimeSettings } from '@/features/agents/components/AgentRuntimeSettings'
import { ModelSettingsTab } from './ModelSettingsTab'
import { KnowledgeTab } from './KnowledgeTab'
import { ToolsTab } from './ToolsTab'
import { OutputSettingsTab } from './OutputSettingsTab'
import { ReleaseTab } from './ReleaseTab'
import { ReleaseDetailsView } from './ReleaseDetailsView'
import { useAgentEditor } from '../AgentEditorContext'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useCreateRelease } from '@/features/agents/hooks'
import { toast } from 'sonner'
import type { Agent, AgentRelease, RuntimeEnvironment } from '@/features/agents/types'

interface AgentInspectorProps {
  agent: Agent
  projectId: string
  agentId: string
  activeTab: string
  environment: RuntimeEnvironment
  environmentRelease: AgentRelease | null
  environmentReleaseLoading?: boolean
  onTabChange: (tab: string) => void
  onCollapse?: () => void
}

function titleCaseEnvironment(environment: RuntimeEnvironment) {
  return environment.charAt(0).toUpperCase() + environment.slice(1)
}

function EditorToolbar({ agent, projectId }: { agent: Agent; projectId: string }) {
  const { loadedReleaseVersion, isDirty, toSnapshot, updateBaseline, resetToBaseline } = useAgentEditor()
  const createRelease = useCreateRelease(agent.id)

  const handleSaveDraft = async () => {
    try {
      const snapshot = toSnapshot()
      const rawResponseFormat = snapshot.response_format
      const responseFormat = rawResponseFormat && typeof rawResponseFormat === 'object' && !Array.isArray(rawResponseFormat)
        ? rawResponseFormat as Record<string, unknown>
        : {}
      const jsonEnabled = responseFormat.enabled === true && responseFormat.type === 'json'
      const currentSchema = responseFormat.schema
      const hasSchema = typeof currentSchema === 'string'
        ? currentSchema.trim().length > 0
        : Boolean(currentSchema && typeof currentSchema === 'object')
      const schema = jsonEnabled && !hasSchema
        ? { message: 'string', confidence: 'float' }
        : currentSchema
      const canonicalSnapshot: Record<string, unknown> = {
        ...snapshot,
        response_format: {
          ...responseFormat,
          strict: true,
          schema,
        },
        output_schema: schema,
      }

      await createRelease.mutateAsync({
        project_id: projectId,
        agent_id: agent.id,
        version: 'draft',
        ...canonicalSnapshot,
      } as any)

      updateBaseline()
      toast.success('Draft saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save draft')
    }
  }

  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border/90 bg-background/25 px-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-[10px] font-medium text-muted">
          {loadedReleaseVersion ? (
            <>Draft based on <span className="font-mono text-primary-light">{loadedReleaseVersion}</span></>
          ) : (
            'Current Draft'
          )}
        </p>
        <p className={isDirty ? 'mt-0.5 text-[9px] text-amber-300/90' : 'mt-0.5 text-[9px] text-muted/60'}>
          {isDirty ? 'Unsaved changes' : loadedReleaseVersion ? 'Ready to save as Draft' : 'Saved'}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <Button
          size="sm"
          variant="ghost"
          className="h-7 w-7 p-0 text-muted"
          onClick={resetToBaseline}
          disabled={!isDirty}
          title="Reset editor to last saved Draft state"
          aria-label="Reset Draft"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </Button>
        <Button
          size="sm"
          className="h-7 px-2.5 text-[10px]"
          onClick={handleSaveDraft}
          loading={createRelease.isPending}
          disabled={!isDirty && !loadedReleaseVersion}
        >
          <Save className="mr-1 h-3 w-3" />
          Save
        </Button>
      </div>
    </div>
  )
}

function EditorTabContent({ agent, projectId, agentId }: { agent: Agent; projectId: string; agentId: string }) {
  const [editorTab, setEditorTab] = useAgentEditorSection()

  return (
    <div className="flex h-full flex-col">
      <EditorToolbar agent={agent} projectId={projectId} />
      <AgentEditorNavigation value={editorTab} onChange={setEditorTab} />
      <ScrollArea className="min-h-0 flex-1">
        {editorTab === 'details' && <AgentOverviewSettings onOpenBehavior={() => setEditorTab('behavior')} />}
        {editorTab === 'behavior' && <AgentBehaviorSettings />}
        {editorTab === 'runtime' && <AgentRuntimeSettings projectId={projectId} />}
        {editorTab === 'output' && <OutputSettingsTab />}
        {editorTab === 'model' && <ModelSettingsTab projectId={projectId} />}
        {editorTab === 'knowledge' && <KnowledgeTab projectId={projectId} agentId={agentId} />}
        {editorTab === 'skills' && <div className="p-4"><AgentSkillsSection projectId={projectId} /></div>}
        {editorTab === 'tools' && <ToolsTab projectId={projectId} agentId={agentId} />}
      </ScrollArea>
    </div>
  )
}

function EnvironmentSnapshotContent({
  environment,
  release,
  loading,
}: {
  environment: Exclude<RuntimeEnvironment, 'draft'>
  release: AgentRelease | null
  loading: boolean
}) {
  const label = titleCaseEnvironment(environment)
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border/90 bg-background/25 px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <Lock className="h-3.5 w-3.5 text-muted" />
          <span className="text-[10px] font-medium text-muted">Viewing immutable {label}</span>
        </div>
        {release ? <Badge variant={environment === 'production' ? 'success' : 'secondary'}>{release.version}</Badge> : null}
      </div>
      <ScrollArea className="min-h-0 flex-1">
        {loading && !release ? (
          <div className="p-4 text-xs text-muted">Loading {label} snapshot…</div>
        ) : release ? (
          <div className="p-4"><ReleaseDetailsView release={release} /></div>
        ) : (
          <div className="p-4">
            <div className="rounded-xl border border-dashed border-border p-4 text-xs leading-5 text-muted">
              {environment === 'staging' ? 'No Agent Staging snapshot has been created yet.' : 'No Agent Production release is active.'}
            </div>
          </div>
        )}
      </ScrollArea>
    </div>
  )
}

export function AgentInspector({
  agent,
  projectId,
  agentId,
  activeTab,
  environment,
  environmentRelease,
  environmentReleaseLoading = false,
  onTabChange,
}: AgentInspectorProps) {
  const resolvedActiveTab = activeTab === 'runtime' ? 'editor' : activeTab
  const editorContent = environment === 'draft'
    ? <EditorTabContent agent={agent} projectId={projectId} agentId={agentId} />
    : <EnvironmentSnapshotContent environment={environment} release={environmentRelease} loading={environmentReleaseLoading} />
  const tabs = [
    {
      id: 'editor',
      label: environment === 'draft' ? 'Editor' : 'Snapshot',
      icon: environment === 'draft' ? <Edit3 className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />,
      content: editorContent,
    },
    {
      id: 'versions',
      label: 'Versions',
      icon: <Rocket className="h-3.5 w-3.5" />,
      content: <div className="versions-tab-compact h-full"><ReleaseTab agentId={agentId} projectId={projectId} /></div>,
    },
  ]

  return (
    <div className="flex w-[400px] shrink-0 flex-col border-l border-border/90 bg-surface/75 shadow-sm shadow-black/5">
      <div className="flex shrink-0 items-center justify-between border-b border-border/90 bg-background/25 px-3 py-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">Inspector</p>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        <InspectorTabs tabs={tabs} defaultTab={resolvedActiveTab} onTabChange={onTabChange} />
      </div>
    </div>
  )
}
