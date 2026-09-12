import { useState } from 'react'
import { ChevronRight, Edit3, Lock, Maximize2, Minimize2, Rocket } from 'lucide-react'
import { AgentConfigurationEditor } from '@/features/agents/components/AgentConfigurationEditor'
import { ReleaseTab } from './ReleaseTab'
import { ReleaseDetailsView } from './ReleaseDetailsView'
import { Badge } from '@/components/ui/Badge'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { cn } from '@/lib/utils'
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
      <div className="flex min-h-[38px] shrink-0 items-center justify-between gap-3 border-b border-border bg-background/20 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <Lock className="h-3 w-3 text-muted-foreground" />
          <span className="truncate font-mono text-[8px] text-muted-foreground">Viewing immutable {label}</span>
        </div>
        {release ? <Badge variant={environment === 'production' ? 'success' : 'secondary'}>{release.version}</Badge> : null}
      </div>
      <ScrollArea className="min-h-0 flex-1">
        {loading && !release ? (
          <div className="p-4 font-mono text-[9px] text-muted-foreground">Loading {label} snapshot…</div>
        ) : release ? (
          <div className="p-3"><ReleaseDetailsView release={release} /></div>
        ) : (
          <div className="p-3">
            <div className="rounded-container border border-dashed border-border bg-background/20 p-4 font-sans text-[10px] leading-4 text-muted-foreground">
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
    ? <AgentConfigurationEditor agent={agent} projectId={projectId} agentId={agentId} />
    : <EnvironmentSnapshotContent environment={environment} release={environmentRelease} loading={environmentReleaseLoading} />

  return (
    <aside
      aria-label="Agent Inspector"
      className={cn(
        'fixed bottom-0 right-0 top-[8rem] z-40 flex w-full max-w-[380px] shrink-0 flex-col border-l border-border bg-surface transition-[width,max-width] duration-200 lg:static lg:z-auto lg:bg-surface/[0.78]',
        expanded ? 'lg:w-[620px] lg:max-w-[65vw]' : 'lg:w-[380px] lg:max-w-[380px]',
      )}
    >
      <div className="flex h-[42px] shrink-0 items-center gap-2 border-b border-border bg-background/20 px-3">
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-[9px] font-bold text-slate-50">Agent settings</p>
        </div>

        <div role="tablist" aria-label="Inspector mode" className="flex shrink-0 items-center rounded-control border border-border bg-control p-[3px]">
          <button
            type="button"
            role="tab"
            aria-selected={resolvedActiveTab === 'editor'}
            onClick={() => onTabChange('editor')}
            className={cn(
              'flex h-[27px] items-center justify-center gap-1 rounded-technical border px-2 font-mono text-[8px] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40',
              resolvedActiveTab === 'editor'
                ? 'border-primary/35 bg-primary/[0.10] text-slate-50'
                : 'border-transparent text-muted-foreground hover:bg-accent/45 hover:text-slate-50',
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
              'flex h-[27px] items-center justify-center gap-1 rounded-technical border px-2 font-mono text-[8px] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40',
              resolvedActiveTab === 'versions'
                ? 'border-primary/35 bg-primary/[0.10] text-slate-50'
                : 'border-transparent text-muted-foreground hover:bg-accent/45 hover:text-slate-50',
            )}
          >
            <Rocket className="h-3 w-3" />
            Versions
          </button>
        </div>

        <button
          type="button"
          onClick={() => setExpanded(current => !current)}
          className="hidden h-7 w-7 items-center justify-center rounded-control border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40 lg:flex"
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
            className="flex h-7 w-7 items-center justify-center rounded-control border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40"
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
