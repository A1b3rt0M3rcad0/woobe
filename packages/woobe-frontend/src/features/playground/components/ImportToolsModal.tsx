import { Shield, Wrench } from 'lucide-react'
import {
  Badge,
  Button,
  Dialog,
  EmptyStatePanel,
  ScrollArea,
  SectionBlock,
  TechnicalListItem,
} from '@woobe/ui'

import { LoadingState } from '@/components/common/LoadingState'
import { useTools } from '@/features/tools/hooks'
import { getToolRuntimeCompatibility } from '@/features/tools/toolRuntimeDependencies'
import type { Tool } from '@/features/tools/types'

function riskVariant(risk?: string | null) {
  const normalized = String(risk || '').toLowerCase()
  if (normalized === 'critical' || normalized === 'high') return 'destructive' as const
  if (normalized === 'medium') return 'warning' as const
  if (normalized === 'low') return 'success' as const
  return 'outline' as const
}

function RiskIndicator({ risk }: { risk?: string | null }) {
  const normalized = String(risk || 'unknown').toLowerCase()
  return (
    <Badge variant={riskVariant(risk)} size="compact" title={`Risk: ${normalized}`}>
      <Shield className="h-icon-sm w-icon-sm" />
      {normalized}
    </Badge>
  )
}

interface ImportToolsModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  importedToolIds: Set<string>
  externalContextFields: ReadonlySet<string>
  projectEnvironmentKeys: ReadonlySet<string> | null
  onImport: (tool: Tool) => void
}

export function ImportToolsModal({
  open,
  onClose,
  projectId,
  importedToolIds,
  externalContextFields,
  projectEnvironmentKeys,
  onImport,
}: ImportToolsModalProps) {
  const { data: allTools = [], isLoading } = useTools(projectId)
  const availableTools = allTools.filter(tool => tool.status === 'active' && !importedToolIds.has(tool.id))
  const handleImport = (tool: Tool) => {
    onImport(tool)
    onClose()
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Import Tool"
      className="flex max-h-dialog max-w-dialog flex-col overflow-hidden"
      contentClassName="min-h-0 flex-1 p-0"
    >
      <div className="flex h-full min-h-0 flex-col">
        <div className="shrink-0 border-b border-border px-ui-lg py-ui-md">
          <SectionBlock
            density="compact"
            eyebrow="Agent capability"
            title="Available Tools"
            description={`${availableTools.length} active Tool${availableTools.length === 1 ? '' : 's'} available. Incompatible Tools remain visible but cannot be imported.`}
            className="border-0 bg-transparent p-0"
          />
        </div>

        <div className="min-h-0 flex-1 p-ui-lg">
          {isLoading ? (
            <LoadingState variant="panel" layout="list" message="Loading tools..." />
          ) : availableTools.length === 0 ? (
            <EmptyStatePanel
              icon={<Wrench className="h-icon-lg w-icon-lg" />}
              title="No active Tools available"
              description="Only active Tools that are not already bound to this Agent Draft are shown here."
            />
          ) : (
            <ScrollArea className="h-full max-h-popover pr-ui-xs">
              <div className="grid gap-ui-xs">
                {availableTools.map((tool) => {
                  const compatibility = getToolRuntimeCompatibility(
                    tool,
                    externalContextFields,
                    projectEnvironmentKeys,
                  )
                  const blockers = [
                    compatibility.missingExternalContext.length > 0
                      ? `Missing External Context: ${compatibility.missingExternalContext.join(', ')}`
                      : null,
                    compatibility.missingProjectEnvironment.length > 0
                      ? `Missing Project Environment: ${compatibility.missingProjectEnvironment.join(', ')}`
                      : null,
                    compatibility.projectEnvironmentUnavailable
                      ? 'Project Environment keys are unavailable'
                      : null,
                  ].filter((item): item is string => Boolean(item))
                  const description = compatibility.compatible
                    ? tool.description || 'No description'
                    : [tool.description || 'No description', ...blockers].join(' · ')

                  return (
                    <TechnicalListItem
                      key={tool.id}
                      label={tool.name}
                      description={description}
                      leading={(
                        <span className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-border bg-control/35 text-primary-light">
                          <Wrench className="h-icon w-icon" />
                        </span>
                      )}
                      meta={<><span>{tool.type}</span><RiskIndicator risk={tool.risk_level} /></>}
                      trailing={(
                        <Badge variant={compatibility.compatible ? 'outline' : 'destructive'} size="compact">
                          {compatibility.compatible ? 'Import' : 'Blocked'}
                        </Badge>
                      )}
                      onClick={compatibility.compatible ? () => handleImport(tool) : undefined}
                    />
                  )
                })}
              </div>
            </ScrollArea>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-between gap-ui-md border-t border-border bg-surface/95 px-ui-lg py-ui-md">
          <p className="font-sans text-product-caption text-muted-foreground">Importing adds the Tool to the current Draft only.</p>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
        </div>
      </div>
    </Dialog>
  )
}
