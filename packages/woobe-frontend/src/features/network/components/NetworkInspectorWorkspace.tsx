import { Rocket, SlidersHorizontal, type LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

import type { AgentNodeId, Environment, NetworkBinding, NetworkVersionOption } from './networkWorkspaceTypes'
import { NetworkConfiguration, type NetworkConfigSection } from './NetworkConfigurationWorkspace'
import { NetworkVersions } from './NetworkVersionsWorkspace'

export type NetworkInspectorSection = 'configuration' | 'versions'
export type { NetworkConfigSection } from './NetworkConfigurationWorkspace'

interface NetworkInspectorWorkspaceProps {
  section: NetworkInspectorSection
  configSection: NetworkConfigSection
  environment: Environment
  bindings: Record<AgentNodeId, NetworkBinding>
  draftBindings: Record<AgentNodeId, NetworkBinding>
  stagingBindings: Record<AgentNodeId, NetworkBinding>
  productionBindings: Record<AgentNodeId, NetworkBinding>
  compositionNode: AgentNodeId
  onSection: (section: NetworkInspectorSection) => void
  onConfigSection: (section: NetworkConfigSection) => void
  onCompositionNode: (node: AgentNodeId) => void
  onUse: (node: AgentNodeId, option: NetworkVersionOption) => void
  onStage: () => void
  onPublish: () => void
  onRollback: () => void
  onLoadNetwork: () => void
}

function SecondaryTabs<T extends string>({
  value,
  items,
  onChange,
}: {
  value: T
  items: Array<{ id: T; label: string; icon: LucideIcon }>
  onChange: (value: T) => void
}) {
  return (
    <div className="flex shrink-0 gap-1 border-b border-border/80 bg-surface/60 p-1.5">
      {items.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          className={cn(
            'flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-[10px] font-medium',
            value === id
              ? 'border-primary/30 bg-primary/10 text-primary-light'
              : 'border-transparent text-muted hover:border-border/70 hover:text-white',
          )}
        >
          <Icon className="h-3.5 w-3.5" />
          {label}
        </button>
      ))}
    </div>
  )
}

export function NetworkInspectorWorkspace({
  section,
  configSection,
  environment,
  bindings,
  draftBindings,
  stagingBindings,
  productionBindings,
  compositionNode,
  onSection,
  onConfigSection,
  onCompositionNode,
  onUse,
  onStage,
  onPublish,
  onRollback,
  onLoadNetwork,
}: NetworkInspectorWorkspaceProps) {
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <SecondaryTabs
        value={section}
        onChange={onSection}
        items={[
          { id: 'configuration', label: 'Configuration', icon: SlidersHorizontal },
          { id: 'versions', label: 'Versions', icon: Rocket },
        ]}
      />
      {section === 'configuration' ? (
        <NetworkConfiguration
          key={compositionNode}
          section={configSection}
          environment={environment}
          bindings={bindings}
          compositionNode={compositionNode}
          onSection={onConfigSection}
          onCompositionNode={onCompositionNode}
          onUse={onUse}
        />
      ) : (
        <NetworkVersions
          draftBindings={draftBindings}
          stagingBindings={stagingBindings}
          productionBindings={productionBindings}
          onStage={onStage}
          onPublish={onPublish}
          onRollback={onRollback}
          onLoadNetwork={onLoadNetwork}
        />
      )}
    </div>
  )
}
