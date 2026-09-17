import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Workflow } from 'lucide-react'
import { toast } from 'sonner'
import { Button, EmptyStatePanel, Field, FieldLabel, Input, MetricTile, PanelHeader, SectionBlock, Select, Textarea } from '@woobe/ui'

import { useUpdateNetworkMetadata } from '@/features/network/hooks'

import { DEFAULT_NETWORK_SETTINGS } from '../editor/networkDefinitionMapper'
import type { NetworkDefinition } from '../types'
import type { NetworkDefinitionChange } from '../editor/types'
import { NetworkInspectorModal } from './NetworkInspectorModal'

export function NetworkOverviewInspector({
  definition,
  readOnly,
  name,
  description,
  onMetadata: _onMetadata,
  onChange,
}: {
  definition: NetworkDefinition
  readOnly: boolean
  name: string
  description: string
  onMetadata: (metadata: { name?: string; description?: string }) => void
  onChange: (change: NetworkDefinitionChange) => void
}) {
  const { projectId, networkId } = useParams<{ projectId: string; networkId: string }>()
  const metadataMutation = useUpdateNetworkMetadata(projectId, networkId)
  const [identityOpen, setIdentityOpen] = useState(false)
  const [runtimeOpen, setRuntimeOpen] = useState(false)
  const [metadataOverridden, setMetadataOverridden] = useState(false)
  const [displayIdentity, setDisplayIdentity] = useState({ name, description })
  const [identityDraft, setIdentityDraft] = useState({ name, description })
  const [runtimeDraft, setRuntimeDraft] = useState({
    ...definition.settings,
    tool_result_max_chars: definition.settings.tool_result_max_chars ?? DEFAULT_NETWORK_SETTINGS.tool_result_max_chars,
  })
  const entryPoint = definition.nodes.find((item) => item.id === definition.root_node_id)?.label ?? 'Not selected'
  const toolResultMaxChars = definition.settings.tool_result_max_chars ?? DEFAULT_NETWORK_SETTINGS.tool_result_max_chars ?? 16_000

  useEffect(() => {
    if (metadataOverridden) return
    setDisplayIdentity({ name, description })
    setIdentityDraft({ name, description })
  }, [description, metadataOverridden, name])

  const saveIdentity = async () => {
    const normalizedName = identityDraft.name.trim()
    if (!normalizedName) {
      toast.error('Network name is required')
      return
    }
    try {
      const saved = await metadataMutation.mutateAsync({
        name: normalizedName,
        description: identityDraft.description.trim(),
      })
      const nextIdentity = { name: saved.name, description: saved.description }
      setDisplayIdentity(nextIdentity)
      setIdentityDraft(nextIdentity)
      setMetadataOverridden(true)
      setIdentityOpen(false)
      toast.success('Network metadata updated')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to update Network metadata')
    }
  }

  return (
    <>
      <PanelHeader
        hierarchy="entity"
        icon={<Workflow className="h-icon w-icon" />}
        title={displayIdentity.name}
        description={`${definition.nodes.length} Agents · ${definition.edges.length} delegations`}
      />

      <div className="space-y-ui-md p-ui-md">
        {definition.nodes.length === 0 ? (
          <EmptyStatePanel
            compact
            title="Build your Network"
            description="Add an Agent, choose the Entry Point, then connect a specialist."
          />
        ) : null}

        <SectionBlock
          density="compact"
          title="Network identity"
          description={displayIdentity.description.trim() || 'No description yet.'}
          actions={<Button type="button" size="sm" variant="outline" onClick={() => { setIdentityDraft(displayIdentity); setIdentityOpen(true) }}>{readOnly ? 'View' : 'Edit'}</Button>}
        >
          <p className="truncate font-mono text-chrome-meta text-muted-foreground">{displayIdentity.name}</p>
        </SectionBlock>

        <SectionBlock density="compact" title="Composition">
          <div className="grid gap-ui-sm sm:grid-cols-2">
            <MetricTile label="Entry point" value={entryPoint} />
            <MetricTile label="Agents" value={definition.nodes.length} />
            <MetricTile label="Delegations" value={definition.edges.length} />
            <MetricTile label="Mode" value={definition.settings.session_mode} />
          </div>
        </SectionBlock>

        <SectionBlock
          density="compact"
          title="Runtime"
          description={`${definition.settings.session_mode} · depth ${definition.settings.max_depth} · ${definition.settings.max_invocations} invocations · ${definition.settings.timeout_seconds}s · tool results ${toolResultMaxChars} chars`}
          actions={<Button type="button" size="sm" variant="outline" onClick={() => { setRuntimeDraft({ ...definition.settings, tool_result_max_chars: toolResultMaxChars }); setRuntimeOpen(true) }}>{readOnly ? 'View' : 'Edit'}</Button>}
        />
      </div>

      {identityOpen ? (
        <NetworkInspectorModal
          title={readOnly ? 'Network identity' : 'Edit Network identity'}
          description="Name and description document the operational purpose of this Network. Metadata changes do not create a Draft revision."
          onClose={() => setIdentityOpen(false)}
          footer={readOnly ? (
            <Button type="button" variant="outline" onClick={() => setIdentityOpen(false)}>Close</Button>
          ) : (
            <>
              <Button type="button" variant="outline" onClick={() => setIdentityOpen(false)}>Cancel</Button>
              <Button type="button" disabled={metadataMutation.isPending} onClick={() => void saveIdentity()}>{metadataMutation.isPending ? 'Saving…' : 'Save'}</Button>
            </>
          )}
        >
          <div className="space-y-ui-md">
            <Field>
              <FieldLabel>Name</FieldLabel>
              <Input disabled={readOnly || metadataMutation.isPending} value={identityDraft.name} onChange={(event) => setIdentityDraft((current) => ({ ...current, name: event.target.value }))} />
            </Field>
            <Field>
              <FieldLabel>Description</FieldLabel>
              <Textarea disabled={readOnly || metadataMutation.isPending} value={identityDraft.description} onChange={(event) => setIdentityDraft((current) => ({ ...current, description: event.target.value }))} />
            </Field>
          </div>
        </NetworkInspectorModal>
      ) : null}

      {runtimeOpen ? (
        <NetworkInspectorModal
          title={readOnly ? 'Runtime settings' : 'Edit runtime settings'}
          description="These limits apply to future Network executions. Tool result max chars controls how much Tool and delegation output can be materialized back to an Agent."
          onClose={() => setRuntimeOpen(false)}
          footer={readOnly ? (
            <Button type="button" variant="outline" onClick={() => setRuntimeOpen(false)}>Close</Button>
          ) : (
            <>
              <Button type="button" variant="outline" onClick={() => setRuntimeOpen(false)}>Cancel</Button>
              <Button type="button" onClick={() => { onChange({ type: 'settings', settings: runtimeDraft }); setRuntimeOpen(false) }}>Save</Button>
            </>
          )}
        >
          <div className="grid gap-ui-md sm:grid-cols-2">
            <Field>
              <FieldLabel>Session mode</FieldLabel>
              <Select disabled={readOnly} value={runtimeDraft.session_mode} onChange={(event) => setRuntimeDraft((current) => ({ ...current, session_mode: event.target.value as 'stateful' | 'stateless' }))} options={[{ value: 'stateful', label: 'Stateful' }, { value: 'stateless', label: 'Stateless' }]} />
            </Field>
            <Field>
              <FieldLabel>Max depth</FieldLabel>
              <Input disabled={readOnly} type="number" min={1} max={8} value={runtimeDraft.max_depth} onChange={(event) => setRuntimeDraft((current) => ({ ...current, max_depth: Number(event.target.value) }))} />
            </Field>
            <Field>
              <FieldLabel>Max invocations</FieldLabel>
              <Input disabled={readOnly} type="number" min={1} max={64} value={runtimeDraft.max_invocations} onChange={(event) => setRuntimeDraft((current) => ({ ...current, max_invocations: Number(event.target.value) }))} />
            </Field>
            <Field>
              <FieldLabel>Timeout</FieldLabel>
              <Input disabled={readOnly} type="number" min={1} max={300} value={runtimeDraft.timeout_seconds} onChange={(event) => setRuntimeDraft((current) => ({ ...current, timeout_seconds: Number(event.target.value) }))} />
            </Field>
            <Field>
              <FieldLabel>Tool result max chars</FieldLabel>
              <Input disabled={readOnly} type="number" min={1000} max={64000} step={1000} value={runtimeDraft.tool_result_max_chars} onChange={(event) => setRuntimeDraft((current) => ({ ...current, tool_result_max_chars: Number(event.target.value) }))} />
            </Field>
          </div>
        </NetworkInspectorModal>
      ) : null}
    </>
  )
}
