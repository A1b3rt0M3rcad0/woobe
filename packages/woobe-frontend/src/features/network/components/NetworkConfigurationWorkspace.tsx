import { GitBranch, Settings2, SlidersHorizontal, Workflow } from 'lucide-react'
import { Alert, AlertDescription, Field, FieldLabel, Input, ScrollArea, SectionBlock, SegmentedControl, Textarea, TechnicalListItem } from '@woobe/ui'

import type { AgentNodeId, Environment, NetworkBinding, NetworkVersionOption } from './networkWorkspaceTypes'
import { CompositionSettings } from './NetworkCompositionSettings'

export type NetworkConfigSection = 'general' | 'composition' | 'routing' | 'runtime'

function GeneralSettings({ readOnly }: { readOnly: boolean }) {
  return (
    <div className="space-y-ui-md">
      <Field>
        <FieldLabel>Network name</FieldLabel>
        <Input disabled={readOnly} defaultValue="Customer Support Network" />
      </Field>
      <Field>
        <FieldLabel>Description</FieldLabel>
        <Textarea disabled={readOnly} defaultValue="Routes customer requests to billing or technical support specialists." />
      </Field>
      <SectionBlock density="compact" title="Entry point">
        <TechnicalListItem label="Coordinator" />
      </SectionBlock>
    </div>
  )
}

function RoutingSettings() {
  return (
    <div className="space-y-ui-sm">
      <TechnicalListItem label="Coordinator → Billing Specialist" description="Condition: billing, invoice, refund or subscription intent." />
      <TechnicalListItem label="Coordinator → Technical Support" description="Condition: API, incident, password or technical error intent." />
    </div>
  )
}

function RuntimeSettings({ readOnly }: { readOnly: boolean }) {
  return (
    <div className="space-y-ui-md">
      <div className="grid gap-ui-sm sm:grid-cols-2">
        <button disabled={readOnly} className="rounded-container border border-primary/35 bg-primary/[0.08] p-ui-md text-left disabled:opacity-50">
          <p className="font-mono text-system-control font-medium text-accent-foreground">Stateful</p>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Persistent Network sessions</p>
        </button>
        <button disabled={readOnly} className="rounded-container border border-border bg-background/25 p-ui-md text-left disabled:opacity-50">
          <p className="font-mono text-system-control font-medium text-accent-foreground">Stateless</p>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Independent requests</p>
        </button>
      </div>
      <Field>
        <FieldLabel>Maximum hops</FieldLabel>
        <Input disabled={readOnly} defaultValue="8" />
      </Field>
    </div>
  )
}

export function NetworkConfiguration({
  section,
  environment,
  bindings,
  compositionNode,
  onSection,
  onCompositionNode,
  onUse,
}: {
  section: NetworkConfigSection
  environment: Environment
  bindings: Record<AgentNodeId, NetworkBinding>
  compositionNode: AgentNodeId
  onSection: (section: NetworkConfigSection) => void
  onCompositionNode: (node: AgentNodeId) => void
  onUse: (node: AgentNodeId, option: NetworkVersionOption) => void
}) {
  const readOnly = environment !== 'draft'

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="scrollbar-thin shrink-0 overflow-x-auto border-b border-border p-ui-xs">
        <SegmentedControl
          value={section}
          onValueChange={(value) => onSection(value as NetworkConfigSection)}
          ariaLabel="Network configuration section"
          items={[
            { value: 'general', label: 'General', icon: <SlidersHorizontal className="h-icon-sm w-icon-sm" /> },
            { value: 'composition', label: 'Composition', icon: <GitBranch className="h-icon-sm w-icon-sm" /> },
            { value: 'routing', label: 'Routing', icon: <Workflow className="h-icon-sm w-icon-sm" /> },
            { value: 'runtime', label: 'Runtime', icon: <Settings2 className="h-icon-sm w-icon-sm" /> },
          ]}
        />
      </div>

      <ScrollArea className="min-h-0 flex-1 overscroll-contain">
        <div className="p-ui-md">
          {readOnly ? (
            <Alert variant="default" className="mb-ui-md">
              <AlertDescription>Viewing an exact read-only {environment} snapshot. Switch to Draft to change Network configuration or composition.</AlertDescription>
            </Alert>
          ) : null}
          {section === 'general' ? <GeneralSettings readOnly={readOnly} /> : null}
          {section === 'composition' ? <CompositionSettings bindings={bindings} compositionNode={compositionNode} readOnly={readOnly} onCompositionNode={onCompositionNode} onUse={onUse} /> : null}
          {section === 'routing' ? <RoutingSettings /> : null}
          {section === 'runtime' ? <RuntimeSettings readOnly={readOnly} /> : null}
        </div>
      </ScrollArea>
    </div>
  )
}
