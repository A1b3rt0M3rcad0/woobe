import { AgentBehaviorDetails } from '@/features/agents/components/AgentBehaviorDetails'
import { SkillSnapshotSummary } from '@/features/skills/SkillSnapshotSummary'
import { Package, Sparkles } from 'lucide-react'

import { Badge } from '@/components/ui/Badge'
import { useKnowledgeVersions } from '@/features/agents/hooks'
import type { AgentRelease } from '@/features/agents/types'
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
    return { name, type, required: required.has(name), description: typeof definition.description === 'string' ? definition.description : undefined, allowedValues }
  })
}

function DetailRow({ label, value }: { label: string; value: unknown }) {
  return <div className="grid min-h-[30px] grid-cols-[128px_minmax(0,1fr)] items-start gap-3 border-b border-border/50 py-2 last:border-b-0"><span className="font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">{label}</span><span className="min-w-0 break-words font-mono text-[9px] text-slate-200">{displayValue(value)}</span></div>
}

function Section({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return <section className="rounded-container border border-border bg-background/25 p-3"><div className="mb-2.5 flex items-center gap-1.5 font-mono text-[8px] font-semibold uppercase tracking-[0.1em] text-slate-300">{icon}{title}</div>{children}</section>
}

export function ReleaseDetailsView({ release }: ReleaseDetailsViewProps) {
  const { data: knowledgeVersions = [] } = useKnowledgeVersions(release.agent_id)
  const knowledgeVersion = knowledgeVersions.find((item) => item.id === release.knowledge_version_id) ?? null
  const runtimeConfig = recordValue(release.runtime_config)
  const ragConfig = recordValue(runtimeConfig.rag)
  const fields = outputFields(release)
  const fallback = release.fallback_provider || release.fallback_model ? `${release.fallback_provider ?? '—'}/${release.fallback_model ?? '—'}` : 'Not configured'

  return <div className="space-y-3">
    <SkillSnapshotSummary runtimeConfig={release.runtime_config} />
    <section className="rounded-container border border-border bg-background/25 p-3">
      <div className="flex items-start justify-between gap-3"><div className="flex min-w-0 items-center gap-2.5"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><Package className="h-3.5 w-3.5" /></span><div className="min-w-0"><p className="font-mono text-[9px] font-semibold text-slate-100">{release.version}</p><p className="mt-1 font-mono text-[8px] text-muted-foreground">Created {formatReleaseDate(release.created_at)}</p></div></div><div className="flex flex-wrap justify-end gap-2"><Badge variant="outline">{sessionModeLabel(release.session_mode)}</Badge><Badge variant={release.status === 'production' ? 'success' : 'secondary'}>{release.status === 'production' ? 'Production' : 'Available Release'}</Badge></div></div>
    </section>

    {release.release_notes ? <Section title="Release description"><p className="whitespace-pre-wrap font-sans text-[9px] leading-4 text-slate-200">{release.release_notes}</p></Section> : null}
    <Section title="Agent details"><DetailRow label="Name" value={release.name} /><DetailRow label="Description" value={release.description} /></Section>
    <AgentBehaviorDetails behavior={release.behavior_spec} legacyPrompt={release.system_prompt} />
    <Section title="Runtime"><DetailRow label="Session Mode" value={sessionModeLabel(release.session_mode)} /><DetailRow label="Context Manager" value={contextAssemblerLabel(release.runtime_config)} /></Section>
    <Section title="Model" icon={<Sparkles className="h-3 w-3" />}><DetailRow label="Provider" value={release.provider} /><DetailRow label="Model" value={release.model} /><DetailRow label="Temperature" value={release.temperature} /><DetailRow label="Maximum output" value={release.max_output_tokens ? `${release.max_output_tokens} tokens` : null} /><DetailRow label="Fallback" value={fallback} /></Section>
    <Section title="Knowledge"><DetailRow label="Knowledge version" value={knowledgeVersion?.version ?? (release.knowledge_version_id ? 'Linked' : 'Not linked')} /><DetailRow label="Collections" value={release.collection_ids?.length ?? 0} /><DetailRow label="Search strategy" value={ragConfig.search_strategy} /><DetailRow label="Candidates" value={ragConfig.candidate_k} /><DetailRow label="Results used" value={ragConfig.top_k} /><DetailRow label="Minimum relevance" value={ragConfig.min_score} /><DetailRow label="Grounding" value={ragConfig.grounding_policy} /></Section>

    <Section title="Output fields">
      {fields.length ? <div className="overflow-hidden rounded-container border border-border/70"><div className="grid grid-cols-[1fr_96px_64px] bg-control/35 px-3 py-2 font-mono text-[8px] font-semibold uppercase tracking-[0.08em] text-muted-foreground"><span>Field</span><span>Type</span><span>Required</span></div>{fields.map((field) => <div key={field.name} className="border-t border-border/60 px-3 py-2.5"><div className="grid grid-cols-[1fr_96px_64px] gap-3 font-mono text-[8px]"><span className="text-slate-100">{field.name}</span><span className="capitalize text-slate-300">{field.type}</span><span className="text-slate-300">{field.required ? 'Yes' : 'No'}</span></div>{field.description ? <p className="mt-1.5 font-sans text-[9px] leading-4 text-muted-foreground">{field.description}</p> : null}{field.allowedValues ? <p className="mt-1 font-mono text-[8px] text-muted-foreground">Allowed values: {field.allowedValues}</p> : null}</div>)}</div> : <p className="font-sans text-[9px] text-muted-foreground">No structured output fields configured.</p>}
    </Section>
  </div>
}
