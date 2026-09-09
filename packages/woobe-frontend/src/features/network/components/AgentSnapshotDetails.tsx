import { AgentBehaviorDetails } from '@/features/agents/components/AgentBehaviorDetails'
import { SkillSnapshotSummary } from '@/features/skills/SkillSnapshotSummary'
import { ChevronDown } from 'lucide-react'

import type { AgentRelease } from '@/features/agents/types'

function formatDate(value?: string) {
  if (!value) return 'Not recorded'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Not recorded'
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function contextManager(runtimeConfig: unknown) {
  const runtime = record(runtimeConfig)
  const selection = record(runtime.context_assembler)
  const name = typeof selection.name === 'string' && selection.name.trim()
    ? selection.name.trim()
    : 'default'
  const version = typeof selection.version === 'string' && selection.version.trim()
    ? selection.version.trim()
    : 'v1'
  return `${name}:${version}`
}

function toolNames(runtimeConfig: unknown): string[] {
  const runtime = record(runtimeConfig)
  const candidates = runtime.tools ?? runtime.enabled_tools ?? runtime.tool_bindings
  if (!Array.isArray(candidates)) return []
  return candidates.flatMap((item) => {
    if (typeof item === 'string') return [item]
    const value = record(item)
    const name = value.name ?? value.tool_name ?? value.slug
    return typeof name === 'string' && name.trim() ? [name.trim()] : []
  })
}

function outputSummary(release: AgentRelease) {
  const response = record(release.response_format)
  const type = typeof response.type === 'string' ? response.type : null
  const enabled = response.enabled !== false
  if (!enabled || type === 'text' || (!type && !release.output_schema)) return 'Text response'
  const schema = record(response.schema ?? release.output_schema)
  const properties = record(schema.properties)
  const fieldCount = Object.keys(properties).length
  return fieldCount > 0
    ? `Structured JSON · ${fieldCount} field${fieldCount === 1 ? '' : 's'}`
    : 'Structured JSON'
}

function SnapshotField({ label, value, mono = false }: { label: string; value: string | number | null | undefined; mono?: boolean }) {
  return (
    <div className="rounded-lg border border-border/75 bg-background/35 p-3">
      <p className="text-[8px] font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 break-words text-[10px] text-slate-200 ${mono ? 'font-mono' : ''}`}>{value == null || value === '' ? 'Not configured' : String(value)}</p>
    </div>
  )
}

export function AgentSnapshotDetails({ release }: { release: AgentRelease }) {
  const tools = toolNames(release.runtime_config)
  const collections = release.collection_ids ?? []
  const output = outputSummary(release)

  return (
    <div className="space-y-5">
      <SkillSnapshotSummary runtimeConfig={release.runtime_config} />
      <section>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          <SnapshotField label="Environment" value={release.snapshot_kind === 'release' ? 'Release' : release.snapshot_kind ?? release.status} />
          <SnapshotField label="Provider" value={release.provider} />
          <SnapshotField label="Model" value={release.model} mono />
          <SnapshotField label="Temperature" value={release.temperature} />
          <SnapshotField label="Max output tokens" value={release.max_output_tokens} />
          <SnapshotField label="Session mode" value={release.session_mode} />
          <SnapshotField label="Context manager" value={contextManager(release.runtime_config)} mono />
        </div>
        <p className="mt-2 text-[9px] text-muted">Created {formatDate(release.created_at)}{release.promoted_at ? ` · Promoted ${formatDate(release.promoted_at)}` : ''}</p>
      </section>

      {release.release_notes ? (
        <section>
          <p className="mb-1.5 text-[9px] font-semibold uppercase tracking-wide text-muted">Release description</p>
          <div className="rounded-xl border border-border/75 bg-background/35 p-3 text-[10px] leading-5 text-slate-200">{release.release_notes}</div>
        </section>
      ) : null}

      <AgentBehaviorDetails behavior={release.behavior_spec} legacyPrompt={release.system_prompt} />

      <div className="grid gap-3 sm:grid-cols-3">
        <section className="rounded-xl border border-border/75 bg-background/35 p-3">
          <p className="text-[8px] font-semibold uppercase tracking-wide text-muted">Knowledge</p>
          <p className="mt-1 text-[10px] font-medium text-slate-200">{collections.length ? `${collections.length} Collection${collections.length === 1 ? '' : 's'}` : 'No Collection configured'}</p>
          {release.knowledge_version_id ? <p className="mt-1 truncate font-mono text-[8px] text-muted">Snapshot {release.knowledge_version_id}</p> : null}
        </section>
        <section className="rounded-xl border border-border/75 bg-background/35 p-3">
          <p className="text-[8px] font-semibold uppercase tracking-wide text-muted">Tools</p>
          <p className="mt-1 text-[10px] font-medium text-slate-200">{tools.length ? `${tools.length} enabled` : 'No Tools configured'}</p>
          {tools.length ? <p className="mt-1 line-clamp-2 text-[8px] leading-4 text-muted">{tools.join(' · ')}</p> : null}
        </section>
        <section className="rounded-xl border border-border/75 bg-background/35 p-3">
          <p className="text-[8px] font-semibold uppercase tracking-wide text-muted">Output</p>
          <p className="mt-1 text-[10px] font-medium text-slate-200">{output}</p>
        </section>
      </div>

      <details className="group overflow-hidden rounded-xl border border-border/75 bg-background/25">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 text-[10px] font-medium text-muted hover:text-white">
          <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
          Advanced technical details
        </summary>
        <div className="border-t border-border/75 p-3">
          <div className="grid grid-cols-2 gap-2">
            <SnapshotField label="Snapshot ID" value={release.id} mono />
            <SnapshotField label="Agent ID" value={release.agent_id} mono />
            <SnapshotField label="Provider model ID" value={release.provider_model_id} mono />
            <SnapshotField label="Model config ID" value={release.model_config_version_id} mono />
            <SnapshotField label="Prompt version ID" value={release.prompt_version_id} mono />
            <SnapshotField label="Contract version ID" value={release.contract_version_id} mono />
          </div>
          <pre className="mt-3 max-h-80 overflow-auto rounded-xl border border-border/75 bg-background/55 p-3 text-[9px] leading-5 text-slate-300 scrollbar-thin">{JSON.stringify(release, null, 2)}</pre>
        </div>
      </details>
    </div>
  )
}