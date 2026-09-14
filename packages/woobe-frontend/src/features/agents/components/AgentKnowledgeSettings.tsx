import { useState } from 'react'
import { BookOpen, Database, Plus, Search, Settings2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  Button,
  EmptyStatePanel,
  PanelHeader,
  SectionBlock,
  Tabs,
  TechnicalListItem,
} from '@woobe/ui'

import { useCreateKnowledgeVersion, useKnowledgeVersions } from '@/features/agents/hooks'
import { SelectKnowledgeVersionModal } from '@/features/knowledge/components/SelectKnowledgeVersionModal'
import { useCollections } from '@/features/knowledge/hooks'
import { DEFAULT_RETRIEVAL_CONFIG, type RagRuntimeConfig } from '@/features/knowledge/ragConfigTypes'
import {
  getRagStrategy,
  mergeRagRuntimeConfig,
  withRagStrategy,
} from '@/features/knowledge/ragStrategyConfig'
import { useRagStrategies } from '@/features/knowledge/ragStrategies'
import type { VectorSnapshot } from '@/features/knowledge/types'
import { ManageKnowledgeModal } from '@/features/playground/components/ManageKnowledgeModal'
import { RagExecutionSettings } from '@/features/playground/components/RagExecutionSettings'
import { RagRuntimeSettings } from '@/features/playground/components/RagRuntimeSettings'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function runtimeConfig(value: Record<string, unknown>): RagRuntimeConfig {
  const rag = record(value.rag)
  return {
    search_strategy: 'similarity',
    candidate_k: typeof rag.candidate_k === 'number' ? rag.candidate_k : DEFAULT_RETRIEVAL_CONFIG.candidate_k,
    top_k: typeof rag.top_k === 'number' ? rag.top_k : DEFAULT_RETRIEVAL_CONFIG.top_k,
    min_score: typeof rag.min_score === 'number' ? rag.min_score : null,
    max_context_chunks: typeof rag.max_context_chunks === 'number' ? rag.max_context_chunks : DEFAULT_RETRIEVAL_CONFIG.max_context_chunks,
    max_chunks_per_document: typeof rag.max_chunks_per_document === 'number' ? rag.max_chunks_per_document : DEFAULT_RETRIEVAL_CONFIG.max_chunks_per_document,
    max_context_chars: typeof rag.max_context_chars === 'number' ? rag.max_context_chars : DEFAULT_RETRIEVAL_CONFIG.max_context_chars,
    query_mode: rag.query_mode === 'current_message' ? 'current_message' : 'conversation_context',
    history_turns: typeof rag.history_turns === 'number' ? rag.history_turns : DEFAULT_RETRIEVAL_CONFIG.history_turns,
    grounding_policy: rag.grounding_policy === 'required' ? 'required' : 'optional',
  }
}

export function AgentKnowledgeSettings({ projectId, agentId }: { projectId: string; agentId: string }) {
  const { data: versions = [] } = useKnowledgeVersions(agentId)
  const { data: collections = [] } = useCollections(projectId)
  const { data: ragStrategies = [], isLoading: ragStrategiesLoading } = useRagStrategies()
  const createKnowledgeVersion = useCreateKnowledgeVersion(agentId)
  const { state, setField } = useAgentEditor()
  const [selectorOpen, setSelectorOpen] = useState(false)
  const [managerOpen, setManagerOpen] = useState(false)
  const [runtimeOpen, setRuntimeOpen] = useState(false)

  const active = versions.find((item) => item.id === state.knowledgeVersionId) || null
  const metadata = active?.snapshot_metadata || {}
  const snapshotId = typeof metadata.vector_snapshot_id === 'string' ? metadata.vector_snapshot_id : null
  const collectionId = active?.collection_ids?.[0] || null
  const collectionName = collections.find((item) => item.id === collectionId)?.name || 'Versioned knowledge'
  const vectorVersion = typeof metadata.vector_snapshot_version === 'string' ? metadata.vector_snapshot_version : '—'
  const runtime = runtimeConfig(state.runtimeConfig)
  const ragStrategy = getRagStrategy(state.runtimeConfig)

  const applySnapshot = async (snapshot: VectorSnapshot): Promise<boolean> => {
    try {
      const created = await createKnowledgeVersion.mutateAsync({ project_id: projectId, agent_id: agentId, snapshot_metadata: { vector_snapshot_id: snapshot.id } } as any)
      setField('knowledgeVersionId', created.id)
      setSelectorOpen(false)
      toast.success(`${snapshot.version} applied to the Agent Draft`)
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to apply knowledge')
      return false
    }
  }

  const sources = (
    <SectionBlock title="Knowledge source" density="compact">
      {active ? (
        <TechnicalListItem
          label={collectionName}
          description={`Knowledge ${active.version} · Vector ${vectorVersion}`}
          meta="Immutable snapshot"
          leading={(
            <span className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-border bg-control text-primary-light">
              <BookOpen className="h-icon w-icon" />
            </span>
          )}
          trailing={(
            <Button
              type="button"
              size="iconSm"
              variant="ghost"
              onClick={() => setField('knowledgeVersionId', null)}
              aria-label="Remove knowledge"
            >
              <Trash2 className="h-icon w-icon text-error" />
            </Button>
          )}
        >
          <div className="mt-ui-sm flex flex-wrap gap-ui-sm border-t border-border pt-ui-sm">
            <Button size="sm" variant="outline" onClick={() => setSelectorOpen(true)}>Change version</Button>
            <Button size="sm" variant="ghost" onClick={() => setManagerOpen(true)}>Manage</Button>
          </div>
        </TechnicalListItem>
      ) : (
        <EmptyStatePanel
          compact
          icon={<Database className="h-icon-lg w-icon-lg" />}
          title="No knowledge selected"
          description="Link an immutable Vector Snapshot to this Agent Draft."
          action={(
            <div className="flex flex-wrap justify-center gap-ui-sm">
              <Button size="sm" variant="outline" onClick={() => setSelectorOpen(true)}>
                <Plus className="h-icon-sm w-icon-sm" />Select knowledge
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setManagerOpen(true)}>Manage</Button>
            </div>
          )}
        />
      )}
    </SectionBlock>
  )

  const retrieval = (
    <SectionBlock
      title="Retrieval"
      description={active ? 'Runtime search policy applied to this Knowledge binding.' : 'Applied when Knowledge is linked.'}
      density="compact"
    >
      <TechnicalListItem
        label="Search behavior"
        description={`Top ${runtime.top_k} from ${runtime.candidate_k} candidates`}
        meta={`${runtime.query_mode === 'current_message' ? 'Current message' : 'Conversation context'} · ${runtime.grounding_policy === 'required' ? 'Required grounding' : 'Optional grounding'}`}
        leading={(
          <span className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-border bg-control text-primary-light">
            <Search className="h-icon w-icon" />
          </span>
        )}
        trailing={(
          <Button size="sm" variant="outline" onClick={() => setRuntimeOpen(true)}>
            <Settings2 className="h-icon-sm w-icon-sm" />Configure
          </Button>
        )}
      />
    </SectionBlock>
  )

  const execution = (
    <SectionBlock
      title="RAG execution"
      description="Choose which registered RAG algorithm executes retrieval for this Agent Draft."
      density="compact"
    >
      <RagExecutionSettings
        value={ragStrategy}
        strategies={ragStrategies}
        isLoading={ragStrategiesLoading}
        onChange={(strategy) => setField('runtimeConfig', withRagStrategy(state.runtimeConfig, strategy))}
      />
    </SectionBlock>
  )

  return (
    <div className="p-ui-md">
      <section aria-label="Knowledge" className="rounded-container border border-border bg-surface/[0.72]">
        <PanelHeader
          icon={<BookOpen className="h-icon w-icon" />}
          title="Knowledge"
          description="Configure sources, retrieval policy, and RAG execution for this Draft."
        />

        <div className="grid gap-ui-md p-ui-md">
          <p className="font-sans text-product-caption text-muted-foreground">
            Keep Knowledge binding, retrieval behavior, and execution strategy explicit and independently configurable.
          </p>
          <Tabs
            defaultTab="sources"
            tabs={[
              { id: 'sources', label: 'Sources', content: sources },
              { id: 'retrieval', label: 'Retrieval', content: retrieval },
              { id: 'execution', label: 'Execution', content: execution },
            ]}
          />
        </div>
      </section>

      <SelectKnowledgeVersionModal
        open={selectorOpen}
        projectId={projectId}
        currentSnapshotId={snapshotId}
        onClose={() => setSelectorOpen(false)}
        onSelect={(snapshot) => { void applySnapshot(snapshot) }}
      />
      <ManageKnowledgeModal
        open={managerOpen}
        projectId={projectId}
        activeBinding={active ? { collectionId, collectionName, knowledgeVersion: active.version, vectorVersion } : null}
        currentSnapshotId={snapshotId}
        onClose={() => setManagerOpen(false)}
        onUseSnapshot={applySnapshot}
      />
      <RagRuntimeSettings
        open={runtimeOpen}
        value={runtime}
        onClose={() => setRuntimeOpen(false)}
        onApply={(value) => setField('runtimeConfig', mergeRagRuntimeConfig(state.runtimeConfig, value))}
      />
    </div>
  )
}
