import { AgentBehaviorDetails } from '@/features/agents/components/AgentBehaviorDetails'
import { SkillSnapshotSummary } from '@/features/skills/SkillSnapshotSummary'
import { Package, Sparkles } from 'lucide-react'

import { Badge } from '@/components/ui/Badge'
import { useKnowledgeVersions } from '@/features/agents/hooks'
import type { AgentRelease } from '@/features/agents/types'
import { contextAssemblerLabel, formatReleaseDate, sessionModeLabel } from './releasePresentation'

type ReleaseDetailsViewProps = {
  release: AgentRelease
}

type OutputField = {
  name: string
  type: string
  required: boolean
  description?: string
  allowedValues?: string
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
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
  const required = new Set(
    Array.isArray(schema.required) ? schema.required.map((item) => String(item)) : [],
  )

  return Object.entries(properties).map(([name, rawDefinition]) => {
    const definition = recordValue(rawDefinition)
    const rawType = definition.type
    const type = Array.isArray(rawType)
      ? rawType.map((item) => String(item)).join(' or ')
      : String(rawType ?? 'Value')
    const allowedValues = Array.isArray(definition.enum)
      ? definition.enum.map((item) => String(item)).join(', ')
      : undefined

    return {
      name,
      type,
      required: required.has(name),
      description: typeof definition.description === 'string'
        ? definition.description
        : undefined,
      allowedValues,
    }
  })
}

function DetailRow({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-3 text-xs">
      <span className="text-muted">{label}</span>
      <span className="min-w-0 break-words text-slate-200">{displayValue(value)}</span>
    </div>
  )
}

export function ReleaseDetailsView({ release }: ReleaseDetailsViewProps) {
  const { data: knowledgeVersions = [] } = useKnowledgeVersions(release.agent_id)
  const knowledgeVersion = knowledgeVersions.find(
    (item) => item.id === release.knowledge_version_id,
  ) ?? null
  const runtimeConfig = recordValue(release.runtime_config)
  const ragConfig = recordValue(runtimeConfig.rag)
  const fields = outputFields(release)
  const fallback = release.fallback_provider || release.fallback_model
    ? `${release.fallback_provider ?? '—'}/${release.fallback_model ?? '—'}`
    : 'Not configured'

  return (
    <div className="space-y-5">
      <SkillSnapshotSummary runtimeConfig={release.runtime_config} />
      <section className="rounded-xl border border-border/80 bg-background/35 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">
              <Package className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="font-mono text-sm font-semibold text-white">{release.version}</p>
              <p className="mt-1 text-[11px] text-muted">Created {formatReleaseDate(release.created_at)}</p>
            </div>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Badge variant="outline">{sessionModeLabel(release.session_mode)}</Badge>
            <Badge variant={release.status === 'production' ? 'success' : 'secondary'}>
              {release.status === 'production' ? 'Production' : 'Available Release'}
            </Badge>
          </div>
        </div>
      </section>

      {release.release_notes ? (
        <section className="rounded-xl border border-border/80 bg-background/35 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Release description</p>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-200">{release.release_notes}</p>
        </section>
      ) : null}

      <section className="space-y-3 rounded-xl border border-border/80 bg-background/35 p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-300">Agent Details</h3>
        <DetailRow label="Name" value={release.name} />
        <DetailRow label="Description" value={release.description} />
      </section>
      <AgentBehaviorDetails behavior={release.behavior_spec} legacyPrompt={release.system_prompt} />
      <section className="space-y-3 rounded-xl border border-border/80 bg-background/35 p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-300">Runtime</h3>
        <DetailRow label="Session Mode" value={sessionModeLabel(release.session_mode)} />
        <DetailRow label="Context Manager" value={contextAssemblerLabel(release.runtime_config)} />
      </section>

      <section className="rounded-xl border border-border/80 bg-background/35 p-4">
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-300">
          <Sparkles className="h-3.5 w-3.5" />Model
        </div>
        <div className="space-y-2.5">
          <DetailRow label="Provider" value={release.provider} />
          <DetailRow label="Model" value={release.model} />
          <DetailRow label="Temperature" value={release.temperature} />
          <DetailRow label="Maximum output" value={release.max_output_tokens ? `${release.max_output_tokens} tokens` : null} />
          <DetailRow label="Fallback" value={fallback} />
        </div>
      </section>

      <section className="rounded-xl border border-border/80 bg-background/35 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Knowledge</p>
        <div className="mt-3 space-y-2.5">
          <DetailRow label="Knowledge version" value={knowledgeVersion?.version ?? (release.knowledge_version_id ? 'Linked' : 'Not linked')} />
          <DetailRow label="Collections" value={release.collection_ids?.length ?? 0} />
          <DetailRow label="Search strategy" value={ragConfig.search_strategy} />
          <DetailRow label="Candidates" value={ragConfig.candidate_k} />
          <DetailRow label="Results used" value={ragConfig.top_k} />
          <DetailRow label="Minimum relevance" value={ragConfig.min_score} />
          <DetailRow label="Grounding" value={ragConfig.grounding_policy} />
        </div>
      </section>

      <section className="rounded-xl border border-border/80 bg-background/35 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Output fields</p>
        {fields.length ? (
          <div className="mt-3 overflow-hidden rounded-lg border border-border/70">
            <div className="grid grid-cols-[1fr_110px_80px] bg-background/60 px-3 py-2 text-[10px] font-semibold uppercase tracking-wide text-muted">
              <span>Field</span><span>Type</span><span>Required</span>
            </div>
            {fields.map((field) => (
              <div key={field.name} className="border-t border-border/60 px-3 py-3">
                <div className="grid grid-cols-[1fr_110px_80px] gap-3 text-xs">
                  <span className="font-mono text-white">{field.name}</span>
                  <span className="capitalize text-slate-300">{field.type}</span>
                  <span className="text-slate-300">{field.required ? 'Yes' : 'No'}</span>
                </div>
                {field.description ? <p className="mt-2 text-[11px] leading-5 text-muted">{field.description}</p> : null}
                {field.allowedValues ? <p className="mt-1 text-[10px] text-muted">Allowed values: {field.allowedValues}</p> : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-xs text-muted">No structured output fields configured.</p>
        )}
      </section>
    </div>
  )
}
