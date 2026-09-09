import { useEffect, useState } from 'react'
import { ChevronRight, Edit3, Lock, Maximize2, Minimize2, Rocket, RotateCcw, Save } from 'lucide-react'
import { AgentEditorNavigation, groupForAgentEditorSection, useAgentEditorSection } from '@/features/agents/components/AgentEditorNavigation'
import { AgentOverviewSettings } from '@/features/agents/components/AgentOverviewSettings'
import { AgentSkillsSection } from '@/features/skills/AgentSkillsSection'
import { AgentBehaviorSettings } from '@/features/agents/components/AgentBehaviorSettings'
import { AgentRuntimeSettings } from '@/features/agents/components/AgentRuntimeSettings'
import { validateAgentEditorState } from '@/features/agents/editorValidation'
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
import { cn } from '@/lib/utils'
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

function EditorToolbar({
  agent,
  projectId,
  onInvalidOutput,
}: {
  agent: Agent
  projectId: string
  onInvalidOutput: () => void
}) {
  const { state, loadedReleaseVersion, setLoadedRelease, isDirty, updateBaseline, resetToBaseline } = useAgentEditor()
  const createRelease = useCreateRelease(agent.id)
  const [saveFailed, setSaveFailed] = useState(false)
  const validation = validateAgentEditorState(state)
  const hasValidationIssue = !validation.valid

  const handleSaveDraft = async () => {
    setSaveFailed(false)
    const capturedState = state
    const result = validateAgentEditorState(capturedState)
    if (!result.valid) {
      onInvalidOutput()
      toast.error(result.issue.message)
      return
    }

    try {
      await createRelease.mutateAsync({
        project_id: projectId,
        agent_id: agent.id,
        version: 'draft',
        ...result.snapshot,
      } as any)

      updateBaseline(capturedState)
      setLoadedRelease(null, null)
      toast.success('Draft saved')
    } catch (err) {
      setSaveFailed(true)
      toast.error(err instanceof Error ? err.message : 'Failed to save draft')
    }
  }

  const status = createRelease.isPending
    ? 'Saving…'
    : saveFailed
      ? 'Save failed'
      : hasValidationIssue
        ? 'Fix Output contract'
        : isDirty
          ? 'Unsaved changes'
          : loadedReleaseVersion
            ? 'Ready to save as Draft'
            : 'Saved'

  return (
    <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border/90 bg-background/25 px-3 py-2.5">
      <div className="min-w-0 flex-1">
        <p className="truncate text-[10px] font-medium text-muted">
          {loadedReleaseVersion ? (
            <>Draft based on <span className="font-mono text-primary-light">{loadedReleaseVersion}</span></>
          ) : (
            'Current Draft'
          )}
        </p>
        <p className={cn(
          'mt-0.5 text-[9px] font-medium',
          saveFailed || hasValidationIssue
            ? 'text-red-300'
            : createRelease.isPending
              ? 'text-primary-light'
              : isDirty
                ? 'text-amber-300/90'
                : 'text-muted/60',
        )}>
          {status}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <Button
          size="sm"
          variant="ghost"
          className="h-8 px-2 text-[10px] text-muted"
          onClick={() => {
            setSaveFailed(false)
            resetToBaseline()
          }}
          disabled={!isDirty || createRelease.isPending}
          title="Discard unsaved Draft changes"
          aria-label="Discard changes"
        >
          <RotateCcw className="mr-1 h-3.5 w-3.5" />
          Discard
        </Button>
        <Button
          size="sm"
          className="h-8 px-2.5 text-[10px]"
          onClick={handleSaveDraft}
          loading={createRelease.isPending}
          disabled={!isDirty && !loadedReleaseVersion}
          aria-invalid={hasValidationIssue || undefined}
        >
          <Save className="mr-1 h-3.5 w-3.5" />
          Save draft
        </Button>
      </div>
    </div>
  )
}

function EditorTabContent({ agent, projectId, agentId }: { agent: Agent; projectId: string; agentId: string }) {
  const [editorSection, setEditorSection] = useAgentEditorSection()
  const activeGroup = groupForAgentEditorSection(editorSection)

  useEffect(() => {
    const target = document.getElementById(`standalone-agent-editor-${editorSection}`)
    if (!target || typeof target.scrollIntoView !== 'function') return
    const scroll = () => target.scrollIntoView({ block: 'start' })
    if (typeof requestAnimationFrame !== 'function') {
      const timeout = window.setTimeout(scroll, 0)
      return () => window.clearTimeout(timeout)
    }
    const frame = requestAnimationFrame(scroll)
    return () => cancelAnimationFrame(frame)
  }, [editorSection])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <EditorToolbar agent={agent} projectId={projectId} onInvalidOutput={() => setEditorSection('output')} />
      <AgentEditorNavigation value={editorSection} onChange={setEditorSection} standalone />
      <ScrollArea className="min-h-0 flex-1">
        {activeGroup.id === 'agent' ? (
          <div className="divide-y divide-border/80">
            <div id="standalone-agent-editor-details" className="scroll-mt-3">
              <AgentOverviewSettings standalone />
            </div>
            <div id="standalone-agent-editor-behavior" className="scroll-mt-3">
              <AgentBehaviorSettings standalone />
            </div>
          </div>
        ) : null}

        {activeGroup.id === 'execution' ? (
          <div className="divide-y divide-border/80">
            <div id="standalone-agent-editor-runtime" className="scroll-mt-3">
              <AgentRuntimeSettings projectId={projectId} standalone />
            </div>
            <div id="standalone-agent-editor-model" className="scroll-mt-3">
              <ModelSettingsTab projectId={projectId} standalone />
            </div>
          </div>
        ) : null}

        {activeGroup.id === 'capabilities' ? (
          <div className="divide-y divide-border/80">
            <div id="standalone-agent-editor-knowledge" className="scroll-mt-3">
              <KnowledgeTab projectId={projectId} agentId={agentId} standalone />
            </div>
            <div id="standalone-agent-editor-tools" className="scroll-mt-3">
              <ToolsTab projectId={projectId} agentId={agentId} standalone />
            </div>
            <div id="standalone-agent-editor-skills" className="scroll-mt-3">
              <AgentSkillsSection projectId={projectId} standalone />
            </div>
          </div>
        ) : null}

        {activeGroup.id === 'output' ? (
          <div id="standalone-agent-editor-output" className="scroll-mt-3">
            <OutputSettingsTab standalone />
          </div>
        ) : null}
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
  onCollapse,
}: AgentInspectorProps) {
  const [expanded, setExpanded] = useState(false)
  const resolvedActiveTab = activeTab === 'versions' ? 'versions' : 'editor'
  const editorLabel = environment === 'draft' ? 'Editor' : 'Snapshot'
  const editorContent = environment === 'draft'
    ? <EditorTabContent agent={agent} projectId={projectId} agentId={agentId} />
    : <EnvironmentSnapshotContent environment={environment} release={environmentRelease} loading={environmentReleaseLoading} />

  return (
    <aside
      aria-label="Agent Inspector"
      className={cn(
        'fixed bottom-0 right-0 top-[8rem] z-40 flex w-full max-w-[400px] shrink-0 flex-col border-l border-border/90 bg-surface shadow-xl shadow-black/20 transition-[width,max-width] duration-200 lg:static lg:z-auto lg:bg-surface/75 lg:shadow-sm lg:shadow-black/5',
        expanded ? 'lg:w-[640px] lg:max-w-[65vw]' : 'lg:w-[400px] lg:max-w-[400px]',
      )}
    >
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border/90 bg-background/25 px-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[11px] font-semibold text-white">Agent settings</p>
        </div>

        <div role="tablist" aria-label="Inspector mode" className="flex shrink-0 items-center rounded-lg border border-border/80 bg-background/35 p-0.5">
          <button
            type="button"
            role="tab"
            aria-selected={resolvedActiveTab === 'editor'}
            onClick={() => onTabChange('editor')}
            className={cn(
              'flex h-8 items-center justify-center gap-1 rounded-md px-2 text-[10px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60',
              resolvedActiveTab === 'editor'
                ? 'bg-surface text-white shadow-sm'
                : 'text-muted hover:text-white',
            )}
          >
            {environment === 'draft' ? <Edit3 className="h-3 w-3" /> : <Lock className="h-3 w-3" />}
            {editorLabel}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={resolvedActiveTab === 'versions'}
            onClick={() => onTabChange('versions')}
            className={cn(
              'flex h-8 items-center justify-center gap-1 rounded-md px-2 text-[10px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60',
              resolvedActiveTab === 'versions'
                ? 'bg-surface text-white shadow-sm'
                : 'text-muted hover:text-white',
            )}
          >
            <Rocket className="h-3 w-3" />
            Versions
          </button>
        </div>

        <button
          type="button"
          onClick={() => setExpanded(current => !current)}
          className="hidden h-8 w-8 items-center justify-center rounded-md text-muted transition-colors hover:bg-accent/60 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60 lg:flex"
          aria-label={expanded ? 'Restore Inspector width' : 'Expand Inspector'}
          title={expanded ? 'Restore Inspector width' : 'Expand Inspector'}
          aria-pressed={expanded}
        >
          {expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
        </button>
        {onCollapse ? (
          <button
            type="button"
            onClick={onCollapse}
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted transition-colors hover:bg-accent/60 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60"
            aria-label="Collapse Inspector"
            title="Collapse Inspector"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        {resolvedActiveTab === 'versions' ? (
          <ScrollArea className="h-full">
            <div className="versions-tab-compact min-h-full"><ReleaseTab agentId={agentId} projectId={projectId} /></div>
          </ScrollArea>
        ) : editorContent}
      </div>
    </aside>
  )
}
