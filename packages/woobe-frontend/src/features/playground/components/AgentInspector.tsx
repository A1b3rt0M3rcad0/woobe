import { ChevronRight, Edit3, Lock, Rocket } from 'lucide-react'
import { EmptyStatePanel, SegmentedControl } from '@woobe/ui'
import { AgentConfigurationEditor } from '@/features/agents/components/AgentConfigurationEditor'
import { ReleaseTab } from './ReleaseTab'
import { ReleaseDetailsView } from './ReleaseDetailsView'
import { Badge } from '@/components/ui/Badge'
import { ScrollArea } from '@/components/ui/ScrollArea'
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
      <div className="flex min-h-control shrink-0 items-center justify-between gap-ui-md border-b border-border bg-background/20 px-ui-md py-ui-sm">
        <div className="flex min-w-0 items-center gap-ui-sm">
          <Lock className="h-icon-sm w-icon-sm text-muted-foreground" />
          <span className="truncate font-mono text-chrome-meta text-muted-foreground">Viewing immutable {label}</span>
        </div>
        {release ? <Badge variant={environment === 'production' ? 'success' : 'secondary'}>{release.version}</Badge> : null}
      </div>
      <ScrollArea className="min-h-0 flex-1">
        {loading && !release ? (
          <div className="p-ui-lg font-mono text-chrome-label text-muted-foreground">Loading {label} snapshot…</div>
        ) : release ? (
          <div className="p-ui-md"><ReleaseDetailsView release={release} /></div>
        ) : (
          <div className="p-ui-md">
            <EmptyStatePanel
              compact
              title={environment === 'staging' ? 'No Staging snapshot' : 'No Production release'}
              description={environment === 'staging' ? 'Create Staging from the current Agent Draft to inspect its immutable snapshot.' : 'Publish an Agent Release to make Production configuration available.'}
            />
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
  const resolvedActiveTab = activeTab === 'versions' ? 'versions' : 'editor'
  const editorLabel = environment === 'draft' ? 'Editor' : 'Snapshot'
  const editorContent = environment === 'draft'
    ? <AgentConfigurationEditor agent={agent} projectId={projectId} agentId={agentId} />
    : <EnvironmentSnapshotContent environment={environment} release={environmentRelease} loading={environmentReleaseLoading} />

  return (
    <aside
      aria-label="Agent Inspector"
      className="fixed bottom-0 right-0 top-playground-inspector z-workspace flex w-[min(94vw,32.5rem)] max-w-[94vw] shrink-0 flex-col border-l border-border bg-surface lg:static lg:z-auto lg:w-inspector-workspace lg:max-w-inspector-workspace lg:bg-surface/[0.78]"
    >
      <div className="flex h-control shrink-0 items-center gap-ui-sm border-b border-border bg-background/20 px-ui-md">
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-chrome-label font-semibold text-slate-50">Agent settings</p>
        </div>

        <SegmentedControl
          ariaLabel="Inspector mode"
          value={resolvedActiveTab}
          onValueChange={onTabChange}
          items={[
            { value: 'editor', label: editorLabel, icon: environment === 'draft' ? <Edit3 className="h-icon-sm w-icon-sm" /> : <Lock className="h-icon-sm w-icon-sm" /> },
            { value: 'versions', label: 'Versions', icon: <Rocket className="h-icon-sm w-icon-sm" /> },
          ]}
          className="shrink-0"
        />

        {onCollapse ? (
          <button
            type="button"
            onClick={onCollapse}
            className="flex h-control-segment w-control-segment items-center justify-center rounded-control border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40"
            aria-label="Collapse Inspector"
            title="Collapse Inspector"
          >
            <ChevronRight className="h-icon w-icon" />
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
