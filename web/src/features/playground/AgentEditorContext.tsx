import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Agent, AgentRelease } from '@/features/agents/types'
import { getRelease } from '@/features/agents/api'
import { useReleases } from '@/features/agents/hooks'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { useProviderModels } from '@/features/provider-models/hooks'
import { useAgentTools } from '@/features/tools/hooks'

export type ResponseFormat = {
  enabled: boolean
  type: 'text' | 'json'
  strict: boolean
  schema: unknown | null
  repair_attempts?: number
}

export type AgentEditorState = {
  name: string
  description: string
  systemPrompt: string
  responseFormat: ResponseFormat
  outputSchema: unknown | null
  provider: string
  model: string
  providerModelId: string | null
  providerCredentialId: string | null
  fallbackProvider: string
  fallbackModel: string
  fallbackProviderModelId: string | null
  fallbackProviderCredentialId: string | null
  baseUrl: string | null
  temperature: number
  maxOutputTokens: number
  collectionIds: string[]
  knowledgeVersionId: string | null
  toolIds: string[]
  runtimeConfig: Record<string, unknown>
}

export interface EditorContextValue {
  state: AgentEditorState
  setField: <K extends keyof AgentEditorState>(key: K, value: AgentEditorState[K]) => void
  setState: (state: AgentEditorState) => void
  toSnapshot: () => Record<string, unknown>
  loadedReleaseId: string | null
  loadedReleaseVersion: string | null
  setLoadedRelease: (id: string | null, version: string | null) => void
  isDirty: boolean
  activeSource: 'current_draft' | 'draft_unsaved'
  resetToBaseline: () => void
  updateBaseline: () => void
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function splitRuntimeConfig(value: unknown): { runtimeConfig: Record<string, unknown>; toolIds: string[]; hasToolsConfig: boolean } {
  const runtimeConfig = recordValue(value)
  const tools = recordValue(runtimeConfig.tools)
  const hasToolsConfig = Object.prototype.hasOwnProperty.call(runtimeConfig, 'tools')
  const toolIds = Array.isArray(tools.tool_ids)
    ? tools.tool_ids.filter((item): item is string => typeof item === 'string')
    : []
  const { tools: _tools, ...rest } = runtimeConfig
  return { runtimeConfig: rest, toolIds, hasToolsConfig }
}

function runtimeConfigSnapshot(state: AgentEditorState): Record<string, unknown> {
  return {
    ...state.runtimeConfig,
    tools: {
      tool_ids: state.toolIds,
    },
  }
}

export function agentToEditorState(agent: Agent, collectionIds?: string[], knowledgeVersionId?: string | null, toolIds?: string[]): AgentEditorState {
  const settings = (agent.settings || {}) as Record<string, unknown>
  const responseFormat = recordValue(settings.response_format)
  const runtime = splitRuntimeConfig(settings.runtime_config)
  return {
    name: agent.name || '',
    description: agent.description || '',
    systemPrompt: agent.system_prompt || '',
    responseFormat: {
      enabled: Boolean(responseFormat.enabled && responseFormat.type === 'json'),
      type: responseFormat.type === 'json' ? 'json' : 'text',
      strict: Boolean(responseFormat.strict),
      schema: responseFormat.schema ?? null,
      repair_attempts: (responseFormat.repair_attempts as number) ?? undefined,
    },
    outputSchema: responseFormat.schema ?? null,
    provider: agent.provider || '',
    model: agent.model || '',
    providerModelId: agent.provider_model_id || null,
    providerCredentialId: agent.provider_credential_id || null,
    fallbackProvider: agent.fallback_provider || '',
    fallbackModel: agent.fallback_model || '',
    fallbackProviderModelId: agent.fallback_provider_model_id || null,
    fallbackProviderCredentialId: agent.fallback_credential_id || null,
    baseUrl: (settings.base_url as string) || null,
    temperature: agent.temperature ?? 0.7,
    maxOutputTokens: agent.max_output_tokens ?? 2048,
    collectionIds: collectionIds || [],
    knowledgeVersionId: knowledgeVersionId ?? null,
    toolIds: toolIds ?? runtime.toolIds,
    runtimeConfig: runtime.runtimeConfig,
  }
}

export function releaseToEditorState(release: AgentRelease, current: AgentEditorState): AgentEditorState {
  const rf = recordValue(release.response_format)
  const runtime = splitRuntimeConfig(release.runtime_config)
  return {
    ...current,
    name: release.name ?? current.name,
    description: release.description ?? current.description,
    systemPrompt: release.system_prompt ?? current.systemPrompt,
    provider: release.provider ?? current.provider,
    model: release.model ?? current.model,
    providerModelId: release.provider_model_id ?? current.providerModelId,
    providerCredentialId: release.provider_credential_id ?? current.providerCredentialId,
    fallbackProvider: release.fallback_provider ?? current.fallbackProvider,
    fallbackModel: release.fallback_model ?? current.fallbackModel,
    fallbackProviderModelId: release.fallback_provider_model_id ?? current.fallbackProviderModelId,
    fallbackProviderCredentialId: release.fallback_credential_id ?? current.fallbackProviderCredentialId,
    baseUrl: release.base_url ?? current.baseUrl,
    temperature: release.temperature ?? current.temperature,
    maxOutputTokens: release.max_output_tokens ?? current.maxOutputTokens,
    collectionIds: release.collection_ids ?? current.collectionIds,
    knowledgeVersionId: release.knowledge_version_id ?? null,
    toolIds: runtime.hasToolsConfig ? runtime.toolIds : current.toolIds,
    runtimeConfig: release.runtime_config == null ? current.runtimeConfig : runtime.runtimeConfig,
    responseFormat: {
      enabled: Boolean(rf.enabled ?? release.output_schema),
      type: rf.type === 'json' ? 'json' : 'text',
      strict: Boolean(rf.strict),
      schema: rf.schema ?? release.output_schema ?? null,
      repair_attempts: rf.repair_attempts as number | undefined,
    },
    outputSchema: release.output_schema ?? current.outputSchema,
  }
}

export function canonicalSnapshot(state: AgentEditorState): Record<string, unknown> {
  let schema = state.responseFormat.schema
  if (typeof schema === 'string') {
    try { schema = JSON.parse(schema) } catch { schema = null }
  }
  return {
    name: state.name,
    description: state.description,
    system_prompt: state.systemPrompt,
    response_format: {
      enabled: state.responseFormat.enabled,
      type: state.responseFormat.type,
      strict: state.responseFormat.strict,
      schema,
      repair_attempts: state.responseFormat.repair_attempts,
    },
    output_schema: schema,
    provider_model_id: state.providerModelId,
    provider: state.provider,
    model: state.model,
    provider_credential_id: state.providerCredentialId,
    fallback_provider_model_id: state.fallbackProviderModelId || undefined,
    fallback_provider: state.fallbackProvider || undefined,
    fallback_model: state.fallbackModel || undefined,
    fallback_credential_id: state.fallbackProviderCredentialId || undefined,
    base_url: state.baseUrl,
    temperature: state.temperature,
    max_output_tokens: state.maxOutputTokens,
    collection_ids: state.collectionIds,
    knowledge_version_id: state.knowledgeVersionId,
    runtime_config: runtimeConfigSnapshot(state),
  }
}

const EditorContext = createContext<EditorContextValue | null>(null)

export function AgentEditorProvider({ agent, projectId, collectionIds: propCollectionIds, knowledgeVersionId, children }: { agent: Agent; projectId?: string; collectionIds?: string[]; knowledgeVersionId?: string | null; children: ReactNode }) {
  const initial = () => agentToEditorState(agent, propCollectionIds, knowledgeVersionId)
  const [state, setState] = useState<AgentEditorState>(initial)
  const [baselineState, setBaselineState] = useState<AgentEditorState>(initial)
  const [loadedReleaseId, setLoadedReleaseId] = useState<string | null>(null)
  const [loadedReleaseVersion, setLoadedReleaseVersion] = useState<string | null>(null)
  const initializedDraft = useRef(knowledgeVersionId !== undefined)
  const { data: releases } = useReleases(agent.id)
  const { data: legacyAgentTools } = useAgentTools(agent.id)
  const { data: credentials } = useCredentials(projectId || '')
  const { data: providerModels } = useProviderModels(projectId || '')

  useEffect(() => {
    const next = agentToEditorState(agent, propCollectionIds, knowledgeVersionId)
    setState(next)
    setBaselineState(next)
    initializedDraft.current = knowledgeVersionId !== undefined
  }, [agent, propCollectionIds, knowledgeVersionId])

  useEffect(() => {
    if (initializedDraft.current || !releases || !legacyAgentTools) return
    initializedDraft.current = true
    const legacyToolIds = legacyAgentTools.map((tool) => tool.id)
    const draft = releases.find((release) => release.status === 'draft')
    if (!draft) {
      setState((previous) => ({ ...previous, toolIds: legacyToolIds }))
      setBaselineState((previous) => ({ ...previous, toolIds: legacyToolIds }))
      return
    }
    let cancelled = false
    void getRelease(agent.id, draft.id)
      .then((release) => {
        if (cancelled) return
        setState((previous) => releaseToEditorState(release, { ...previous, toolIds: legacyToolIds }))
        setBaselineState((previous) => releaseToEditorState(release, { ...previous, toolIds: legacyToolIds }))
      })
      .catch(() => undefined)
    return () => { cancelled = true }
  }, [agent.id, releases, legacyAgentTools])

  useEffect(() => {
    if (!loadedReleaseId) return
    let cancelled = false
    void getRelease(agent.id, loadedReleaseId)
      .then((release) => {
        if (cancelled) return
        setState((previous) => releaseToEditorState(release, previous))
      })
      .catch(() => undefined)
    return () => { cancelled = true }
  }, [agent.id, loadedReleaseId])

  useEffect(() => {
    if (state.providerModelId || !providerModels?.length || !state.providerCredentialId || !state.model) return
    const providerModel = providerModels.find((item) => item.provider_credential_id === state.providerCredentialId && item.model === state.model)
    if (providerModel) setState((previous) => previous.providerModelId ? previous : { ...previous, providerModelId: providerModel.id })
  }, [state.providerModelId, state.providerCredentialId, state.model, providerModels])

  useEffect(() => {
    if (state.fallbackProviderModelId || !providerModels?.length || !state.fallbackProviderCredentialId || !state.fallbackModel) return
    const providerModel = providerModels.find((item) => item.provider_credential_id === state.fallbackProviderCredentialId && item.model === state.fallbackModel)
    if (providerModel) setState((previous) => previous.fallbackProviderModelId ? previous : { ...previous, fallbackProviderModelId: providerModel.id })
  }, [state.fallbackProviderModelId, state.fallbackProviderCredentialId, state.fallbackModel, providerModels])

  useEffect(() => {
    if (!state.providerModelId || !providerModels?.length) return
    const providerModel = providerModels.find((item) => item.id === state.providerModelId)
    if (!providerModel) return
    const credential = credentials?.find((item) => item.id === providerModel.provider_credential_id)
    setState((previous) => {
      const provider = providerModel.provider || credential?.provider || previous.provider
      const model = providerModel.model || previous.model
      const providerCredentialId = providerModel.provider_credential_id || previous.providerCredentialId
      const baseUrl = credential?.metadata?.base_url || previous.baseUrl
      if (previous.provider === provider && previous.model === model && previous.providerCredentialId === providerCredentialId && previous.baseUrl === baseUrl) return previous
      return { ...previous, provider, model, providerCredentialId, baseUrl }
    })
  }, [state.providerModelId, providerModels, credentials])

  useEffect(() => {
    if (!state.fallbackProviderModelId || !providerModels?.length) return
    const providerModel = providerModels.find((item) => item.id === state.fallbackProviderModelId)
    if (!providerModel) return
    const credential = credentials?.find((item) => item.id === providerModel.provider_credential_id)
    setState((previous) => {
      const fallbackProvider = providerModel.provider || credential?.provider || previous.fallbackProvider
      const fallbackModel = providerModel.model || previous.fallbackModel
      const fallbackProviderCredentialId = providerModel.provider_credential_id || previous.fallbackProviderCredentialId
      if (previous.fallbackProvider === fallbackProvider && previous.fallbackModel === fallbackModel && previous.fallbackProviderCredentialId === fallbackProviderCredentialId) return previous
      return { ...previous, fallbackProvider, fallbackModel, fallbackProviderCredentialId }
    })
  }, [state.fallbackProviderModelId, providerModels, credentials])

  useEffect(() => {
    if (state.providerModelId || !state.providerCredentialId || !credentials?.length) return
    const credential = credentials.find((item) => item.id === state.providerCredentialId)
    if (!credential) return
    setState((previous) => {
      const provider = credential.provider
      const model = credential.metadata?.model || credential.metadata?.model_name || previous.model
      const baseUrl = credential.metadata?.base_url || previous.baseUrl
      if (previous.provider === provider && previous.model === model && previous.baseUrl === baseUrl) return previous
      return { ...previous, provider, model, baseUrl }
    })
  }, [state.providerModelId, state.providerCredentialId, credentials])

  useEffect(() => {
    if (state.fallbackProviderModelId || !state.fallbackProviderCredentialId || !credentials?.length) return
    const credential = credentials.find((item) => item.id === state.fallbackProviderCredentialId)
    if (credential) setState((previous) => ({ ...previous, fallbackProvider: credential.provider, fallbackModel: credential.metadata?.model || credential.metadata?.model_name || previous.fallbackModel }))
  }, [state.fallbackProviderModelId, state.fallbackProviderCredentialId, credentials])

  const setField = useCallback(<K extends keyof AgentEditorState>(key: K, value: AgentEditorState[K]) => setState((previous) => ({ ...previous, [key]: value })), [])
  const setLoadedRelease = useCallback((id: string | null, version: string | null) => { setLoadedReleaseId(id); setLoadedReleaseVersion(version) }, [])
  const toSnapshot = useCallback((): Record<string, unknown> => canonicalSnapshot(state), [state])
  const snapshot = useMemo(() => JSON.stringify(canonicalSnapshot(state)), [state])
  const baselineSnapshot = useMemo(() => JSON.stringify(canonicalSnapshot(baselineState)), [baselineState])
  const isDirty = snapshot !== baselineSnapshot
  const activeSource: 'current_draft' | 'draft_unsaved' = isDirty ? 'draft_unsaved' : 'current_draft'
  const resetToBaseline = useCallback(() => { setState(baselineState); setLoadedRelease(null, null) }, [baselineState, setLoadedRelease])
  const updateBaseline = useCallback(() => setBaselineState(state), [state])

  return <EditorContext.Provider value={{ state, setField, setState, toSnapshot, loadedReleaseId, loadedReleaseVersion, setLoadedRelease, isDirty, activeSource, resetToBaseline, updateBaseline }}>{children}</EditorContext.Provider>
}

export function useAgentEditor(): EditorContextValue {
  const context = useContext(EditorContext)
  if (!context) throw new Error('useAgentEditor must be used within AgentEditorProvider')
  return context
}
