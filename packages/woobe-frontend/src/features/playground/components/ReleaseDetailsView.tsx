import { Package, Sparkles } from 'lucide-react'
import { Badge, EmptyStatePanel, SectionBlock, TechnicalListItem } from '@woobe/ui'

import { AgentBehaviorDetails } from '@/features/agents/components/AgentBehaviorDetails'
import { executionStrategyFromRuntimeConfig } from '@/features/agents/executionStrategy'
import { useKnowledgeVersions } from '@/features/agents/hooks'
import type { AgentRelease } from '@/features/agents/types'
import { SkillSnapshotSummary } from '@/features/skills/SkillSnapshotSummary'
import { contextAssemblerLabel, formatReleaseDate, sessionModeLabel } from './releasePresentation'

type ReleaseDetailsViewProps = { release: AgentRelease }
type OutputField = { name: string; type: string; required: boolean; description?: string; allowedValues?: string }

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Enabled' : 'Disabled'
  if (Array.isArray(value)) return value.length ? value.join(', ') : '—'
  return String(value)
}

function outputFields(release: AgentRelease): OutputField[] {
  const schema = recordValue(release.output_schema ?? release.response_format)
  const properties = recordValue(schema.properties)
  const required = new Set(Array.isArray(schema.required) ? schema.required.map((item) => String(item)) : [])
  return Object.entries(properties).map(([name, rawDefinition]) => {
    const definition = recordValue(rawDefinition)
    const rawType = definition.type
    const type = Array.isArray(rawType) ? rawType.map((item) => String(item)).join(' or ') : String(rawType ?? 'Value')
    const allowedValues = Array.isArray(definition.enum) ? definition.enum.map((item) => String(item)).join(', ') : undefined
    return {
      name,
      type,
      required: required.has(name),
      description: typeof definition.description === 'string' ? definition.description : undefined,
      allowedValues,
    }
  })
}

function DetailRow({ label, value }: { label: string; value: unknown }) {
  return <TechnicalListItem label={label} description={displayValue(value)} />
}

export function ReleaseDetailsView({ release }: ReleaseDetailsViewProps) {
  const { data: knowledgeVersions = [] } = useKnowledgeVersions(release.agent_id)
  const knowledgeVersion = knowledgeVersions.find((item) => item.id === release.knowledge_version_id) ?? null
  const runtimeConfig = recordValue(release.runtime_config)
  const ragConfig = recordValue(runtimeConfig.rag)
  const executionStrategy = executionStrategyFromRuntimeConfig(runtimeConfig)
  const fields = outputFields(release)
  const fallback = release.fallback_provider || release.fallback_model
    ? `${release.fallback_provider ?? '—'}/${release.fallback_model ?? '—'}`
    : 'Not configured'

  return (
    <div className="grid gap-ui-md">
      <SkillSnapshotSummary runtimeConfig={release.runtime_config} />

      <TechnicalListItem
        label={release.version}
        description={`Created ${formatReleaseDate(release.created_at)}`}
        leading={(
          <span className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-border bg-control text-primary-light">
            <Package className="h-icon w-icon" />
          </span>
        )}
        meta={(
          <>
            <Badge variant="outline" size="compact">{sessionModeLabel(release.session_mode)}</Badge>
            <Badge variant={release.status === 'production' ? 'success' : 'secondary'} size="compact">
              {release.status === 'production' ? 'Production' : 'Available Release'}
            </Badge>
          </>
        )}
      />

      {release.release_notes ? (
        <SectionBlock title="Release description" density="compact">
          <p className="whitespace-pre-wrap font-sans text-product-small leading-5 text-accent-foreground/85">{release.release_notes}</p>
        </SectionBlock>
      ) : null}

      <SectionBlock title="Agent Details" density="compact">
        <div className="grid gap-ui-xs sm:grid-cols-2">
          <DetailRow label="Name" value={release.name} />
          <DetailRow label="Description" value={release.description} />
        </div>
      </SectionBlock>

      <AgentBehaviorDetails behavior={release.behavior_spec} legacyPrompt={release.system_prompt} />

      <SectionBlock title="Runtime" density="compact">
        <div className="grid gap-ui-xs sm:grid-cols-2">
          <DetailRow label="Execution Strategy" value={executionStrategy === 'standard' ? 'Standard' : executionStrategy} />
          <DetailRow label="Session Mode" value={sessionModeLabel(release.session_mode)} />
          <DetailRow label="Context Manager" value={contextAssemblerLabel(release.runtime_config)} />
        </div>
      </SectionBlock>

      <SectionBlock title="Model" density="compact" actions={<Sparkles className="h-icon w-icon text-primary-light" />}>
        <div className="grid gap-ui-xs sm:grid-cols-2">
          <DetailRow label="Provider" value={release.provider} />
          <DetailRow label="Model" value={release.model} />
          <DetailRow label="Temperature" value={release.temperature} />
          <DetailRow label="Maximum output" value={release.max_output_tokens ? `${release.max_output_tokens} tokens` : null} />
          <DetailRow label="Fallback" value={fallback} />
        </div>
      </SectionBlock>

      <SectionBlock title="Knowledge" density="compact">
        <div className="grid gap-ui-xs sm:grid-cols-2">
          <DetailRow label="Knowledge version" value={knowledgeVersion?.version ?? (release.knowledge_version_id ? 'Linked' : 'Not linked')} />
          <DetailRow label="Collections" value={release.collection_ids?.length ?? 0} />
          <DetailRow label="Search strategy" value={ragConfig.search_strategy} />
          <DetailRow label="Candidates" value={ragConfig.candidate_k} />
          <DetailRow label="Results used" value={ragConfig.top_k} />
          <DetailRow label="Minimum relevance" value={ragConfig.min_score} />
          <DetailRow label="Grounding" value={ragConfig.grounding_policy} />
        </div>
      </SectionBlock>

      <SectionBlock title="Output fields" density="compact">
        {fields.length ? (
          <div className="grid gap-ui-xs">
            {fields.map((field) => (
              <TechnicalListItem
                key={field.name}
                label={field.name}
                description={field.description || 'No field description'}
                meta={(
                  <>
                    <Badge variant="outline" size="compact">{field.type}</Badge>
                    <Badge variant={field.required ? 'default' : 'secondary'} size="compact">{field.required ? 'Required' : 'Optional'}</Badge>
                    {field.allowedValues ? <span>Allowed: {field.allowedValues}</span> : null}
                  </>
                )}
              />
            ))}
          </div>
        ) : (
          <EmptyStatePanel compact title="No structured output fields configured" />
        )}
      </SectionBlock>
    </div>
  )
}
