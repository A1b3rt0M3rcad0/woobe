import { behaviorFromSpec, behaviorToSpec, type AgentBehavior } from '@/features/agents/behavior'
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Agent, AgentRelease, ExternalContextContract } from '@/features/agents/types'
import { getRelease } from '@/features/agents/api'
import { useReleases } from '@/features/agents/hooks'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { useProviderModels } from '@/features/provider-models/hooks'
import { useAgentTools } from '@/features/tools/hooks'
import type { McpToolPermission, Tool } from '@/features/tools/types'

export type ResponseFormat = {
  enabled: boolean
  type: 'text' | 'json'
  strict: boolean
  schema: unknown | null
  repair_attempts?: number
}

export type AgentSessionMode = 'stateful' | 'stateless'
export type AgentToolPermissions = Record<string, Record<string, McpToolPermission>>

export type AgentEditorState = {
  name: string
  description: string
  behavior: AgentBehavior
  sessionMode: AgentSessionMode
  responseFormat: ResponseFormat
  outputSchema: unknown | null
  externalContextContract: ExternalContextContract | string | null
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
  toolPermissions: AgentToolPermissions
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
  updateBaseline: (confirmedState?: AgentEditorState) => void
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function normalizePermission(value: unknown): McpToolPermission {
  const raw = recordValue(value)
  const mode = raw.mode === 'allow' || raw.mode === 'deny' || raw.mode === 'review' ? raw.mode : 'review'
  const riskLevel = typeof raw.risk_level === 'string' ? raw.risk_level : undefined
  return riskLevel ? { mode, risk_level: riskLevel } : { mode }
}

function normalizeToolPermissions(value: unknown): AgentToolPermissions {
  const result: AgentToolPermissions = {}
  for (const [toolId, rawPermissions] of Object.entries(recordValue(value))) {
    const permissions: Record<string, McpToolPermission> = {}
    for (const [remoteToolName, rawPermission] of Object.entries(recordValue(rawPermissions))) {
      permissions[remoteToolName] = normalizePermission(rawPermission)
    }
    result[toolId] = permissions
  }
  return result
}

export function childPermissionsFromToolConfig(value: unknown): Record<string, McpToolPermission> {
  const config = recordValue(value)
  const permissions: Record<string, McpToolPermission> = {}

  const discoveredTools = Array.isArray(config.discovered_tools) ? config.discovered_tools : []
  for (const rawDiscoveredTool of discoveredTools) {
    const discoveredTool = recordValue(rawDiscoveredTool)
    const name = typeof discoveredTool.name === 'string' && discoveredTool.name.trim()
      ? discoveredTool.name.trim()
      : null
    if (!name) continue
    permissions[name] = normalizePermission(discoveredTool.permission)
  }

  const routes = Array.isArray(config.routes) ? config.routes : []
  for (const rawRoute of routes) {
    const route = recordValue(rawRoute)
    const routeId = typeof route.id === 'string' && route.id.trim()
      ? route.id.trim()
      : typeof route.operation_id === 'string' && route.operation_id.trim()
        ? route.operation_id.trim()
        : null
    if (!routeId) continue
    const permission = Object.keys(recordValue(route.permission)).length > 0
      ? route.permission
      : {
          mode: route.default_permission,
          risk_level: route.risk_level,
        }
    permissions[routeId] = normalizePermission(permission)
  }

  return permissions
}

export function toolPermissionsFromSnapshots(value: unknown): AgentToolPermissions {
  if (!Array.isArray(value)) return {}
  const result: AgentToolPermissions = {}
  for (const rawSnapshot of value) {
    const snapshot = recordValue(rawSnapshot)
    const toolId = typeof snapshot.id === 'string' ? snapshot.id : null
    if (!toolId) continue
    result[toolId] = childPermissionsFromToolConfig(snapshot.config)
  }
  return result
}

export function toolPermissionsFromTools(tools: Tool[]): AgentToolPermissions {
  const result: AgentToolPermissions = {}
  for (const tool of tools) {
    result[tool.id] = childPermissionsFromToolConfig(tool.config)
  }
  return result
}

function mergeToolPermissions(base: AgentToolPermissions, overrides: AgentToolPermissions): AgentToolPermissions {
  const merged: AgentToolPermissions = { ...base }
  for (const [toolId, permissions] of Object.entries(overrides)) {
    merged[toolId] = { ...(base[toolId] || {}), ...permissions }
  }
  return merged
}

function normalizeContextManagerSelection(value: unknown): Record<string, unknown> | null {
  const raw = recordValue(value)
  const legacyStrategyName = typeof raw.strategy_name === 'string' ? raw.strategy_name.trim() : ''
  const selected = typeof value === 'string'
    ? value.trim()
    : legacyStrategyName || (typeof raw.name === 'string' ? raw.name.trim() : '')
  if (!selected) return null
  const normalizedSelection = selected.toLowerCase()
  const normalized = ['stdcm', 'default', 'stdcm:v1', 'stdcm:v2', 'default:v1'].includes(normalizedSelection)
    ? 'standard'
    : normalizedSelection
  return { name: normalized }
}

function splitRuntimeConfig(value: unknown): { runtimeConfig: Record<string, unknown>; toolIds: string[]; toolPermissions: AgentToolPermissions; hasToolsConfig: boolean } {
  const runtimeConfig = recordValue(value)
  const tools = recordValue(runtimeConfig.tools)
  const hasToolsConfig = Object.prototype.hasOwnProperty.call(runtimeConfig, 'tools')
  const toolIds = Array.isArray(tools.tool_ids)
    ? tools.tool_ids.filter((item): item is string => typeof item === 'string')
    : []
  const snapshotPermissions = toolPermissionsFromSnapshots(tools.snapshots)
  const explicitPermissions = normalizeToolPermissions(tools.permissions)
  const toolPermissions = mergeToolPermissions(snapshotPermissions, explicitPermissions)
  const contextAssembler = normalizeContextManagerSelection(runtimeConfig.context_assembler)
  const { tools: _tools, context_assembler: _contextAssembler, ...rest } = runtimeConfig
  return {
    runtimeConfig: contextAssembler ? { ...rest, context_assembler: contextAssembler } : rest,
    toolIds,
    toolPermissions,
    hasToolsConfig,
  }
}

function runtimeConfigSnapshot(state: AgentEditorState): Record<string, unknown> {
  const permissions = Object.fromEntries(
    state.toolIds
      .filter((toolId) => state.toolPermissions[toolId])
      .map((toolId) => [toolId, state.toolPermissions[toolId]]),
  )
  return {
    ...state.runtimeConfig,
    tools: {
      tool_ids: state.toolIds,
      permissions,
    },
  }
}

function externalContextContractValue(value: unknown): ExternalContextContract | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const raw = recordValue(value)
  const legacyValue = raw.fields
  const legacy = recordValue(legacyValue)
  const isLegacy = Object.prototype.hasOwnProperty.call(raw, 'fields') && legacyValue !== null && typeof legacyValue === 'object' && !Array.isArray(legacyValue)
  return (isLegacy ? legacy : raw) as ExternalContextContract
}

export function agentToEditorState(agent: Agent, collectionIds?: string[], knowledgeVersionId?: string | null, toolIds?: string[]): AgentEditorState {
  const settings = (agent.settings || {}) as Record<string, unknown>
  const responseFormat = recordValue(settings.response_format)
  const runtime = splitRuntimeConfig(settings.runtime_config)
  const savedKnowledgeVersionId = typeof settings.knowledge_version_id === 'string' ? settings.knowledge_version_id : null
  return {
    name: agent.name || '',
    description: agent.description || '',
    behavior: behaviorFromSpec(agent.behavior_spec, agent.system_prompt || ''),
    sessionMode: agent.session_mode === 'stateless' ? 'stateless' : 'stateful',
    responseFormat: {
      enabled: Boolean(responseFormat.enabled && responseFormat.type === 'json'),
      type: responseFormat.type === 'json' ? 'json' : 'text',
      strict: true,
      schema: responseFormat.schema ?? null,
      repair_attempts: (responseFormat.repair_attempts as number) ?? undefined,
    },
    outputSchema: responseFormat.schema ?? null,
    externalContextContract: externalContextContractValue(settings.external_context_contract),
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
    knowledgeVersionId: knowledgeVersionId !== undefined ? knowledgeVersionId : savedKnowledgeVersionId,
    toolIds: toolIds ?? runtime.toolIds,
    toolPermissions: runtime.toolPermissions,
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
    behavior: behaviorFromSpec(release.behavior_spec, release.system_prompt ?? ''),
    sessionMode: release.session_mode === 'stateless'
      ? 'stateless'
      : release.session_mode === 'stateful'
        ? 'stateful'
        : current.sessionMode,
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
    toolPermissions: runtime.hasToolsConfig ? runtime.toolPermissions : current.toolPermissions,
    runtimeConfig: release.runtime_config == null ? current.runtimeConfig : runtime.runtimeConfig,
    responseFormat: {
      enabled: Boolean(rf.enabled ?? release.output_schema),
      type: rf.type === 'json' ? 'json' : 'text',
      strict: true,
      schema: rf.schema ?? release.output_schema ?? null,
      repair_attempts: rf.repair_attempts as number | undefined,
    },
    outputSchema: release.output_schema ?? current.outputSchema,
    externalContextContract: externalContextContractValue(release.external_context_contract),
  }
}

export function canonicalSnapshot(state: AgentEditorState): Record<string, unknown> {
  let schema = state.responseFormat.schema
  if (typeof schema === 'string') {
    try { schema = JSON.parse(schema) } catch { /* Preserve invalid raw editor text until a validation boundary. */ }
  }
  let externalContextContract: unknown = state.externalContextContract
  if (typeof externalContextContract === 'string') {
    try { externalContextContract = JSON.parse(externalContextContract) } catch { /* Preserve invalid raw editor text until validation. */ }
  }
  return {
    name: state.name,
    description: state.description,
    behavior_spec: behaviorToSpec(state.behavior),
    session_mode: state.sessionMode,
    response_format: {
      enabled: state.responseFormat.enabled,
      type: state.responseFormat.type,
      strict: true,
      schema,
      repair_attempts: state.responseFormat.repair_attempts,
    },
    output_schema: schema,
    external_context_contract: externalContextContract,
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

function mergeHydratedState(
  previous: AgentEditorState,
  next: AgentEditorState,
  editedFields: ReadonlySet<keyof AgentEditorState>,
): AgentEditorState {
  const merged = { ...previous }
  for (const key of Object.keys(next) as Array<keyof AgentEditorState>) {
    if (editedFields.has(key)) continue
    ;(merged as Record<keyof AgentEditorState, AgentEditorState[keyof AgentEditorState]>)[key] = next[key]
  }
  return merged
}

function sameEditorValue(left: AgentEditorState[keyof AgentEditorState], right: AgentEditorState[keyof AgentEditorState]) {
  return JSON.stringify(left) === JSON.stringify(right)
}

const EditorContext = createContext<EditorContextValue | null>(null)

export function AgentEditorProvider({ agent, projectId, collectionIds: propCollectionIds, knowledgeVersionId, children }: { agent: Agent; projectId?: string; collectionIds?: string[]; knowledgeVersionId?: string | null; children: ReactNode }) {
  const initial = () => agentToEditorState(agent, propCollectionIds, knowledgeVersionId)
  const [state, setEditorState] = useState<AgentEditorState>(initial)
  const [baselineState, setBaselineState] = useState<AgentEditorState>(initial)
  const [loadedReleaseId, setLoadedReleaseId] = useState<string | null>(null)
  const [loadedReleaseVersion, setLoadedReleaseVersion] = useState<string | null>(null)
  const editedFields = useRef<Set<keyof AgentEditorState>>(new Set())
  const initializedDraft = useRef(knowledgeVersionId !== undefined)
  const editorResetKey = `${agent.id}|${knowledgeVersionId === undefined ? '__draft__' : knowledgeVersionId ?? ''}|${(propCollectionIds ?? []).join(',')}`
  const lastEditorResetKey = useRef(editorResetKey)
  const { data: releases } = useReleases(agent.id)
  const { data: legacyAgentTools } = useAgentTools(agent.id)
  const { data: credentials } = useCredentials(projectId || '')
  const { data: providerModels } = useProviderModels(projectId || '')

  const hydrateState = useCallback((buildNext: (previous: AgentEditorState) => AgentEditorState) => {
    setEditorState((previous) => mergeHydratedState(previous, buildNext(previous), editedFields.current))
    setBaselineState((previous) => mergeHydratedState(previous, buildNext(previous), editedFields.current))
  }, [])

  useEffect(() => {
    if (lastEditorResetKey.current === editorResetKey) return
    lastEditorResetKey.current = editorResetKey
    const next = agentToEditorState(agent, propCollectionIds, knowledgeVersionId)
    editedFields.current.clear()
    setEditorState(next)
    setBaselineState(next)
    setLoadedReleaseId(null)
    setLoadedReleaseVersion(null)
    initializedDraft.current = knowledgeVersionId !== undefined
  }, [agent, editorResetKey, propCollectionIds, knowledgeVersionId])

  useEffect(() => {
    if (initializedDraft.current || !releases || !legacyAgentTools) return
    initializedDraft.current = true
    const legacyToolIds = legacyAgentTools.map((tool) => tool.id)
    const legacyToolPermissions = toolPermissionsFromTools(legacyAgentTools)
    const draft = releases.find((release) => release.status === 'draft')
    if (!draft) {
      hydrateState((previous) => ({ ...previous, toolIds: legacyToolIds, toolPermissions: legacyToolPermissions }))
      return
    }
    let cancelled = false
    void getRelease(agent.id, draft.id)
      .then((release) => {
        if (cancelled) return
        hydrateState((previous) => releaseToEditorState(release, { ...previous, toolIds: legacyToolIds, toolPermissions: legacyToolPermissions }))
      })
      .catch(() => undefined)
    return () => { cancelled = true }
  }, [agent.id, releases, legacyAgentTools, hydrateState])

  useEffect(() => {
    if (!loadedReleaseId) return
    let cancelled = false
    void getRelease(agent.id, loadedReleaseId)
      .then((release) => {
        if (cancelled) return
        hydrateState((previous) => releaseToEditorState(release, previous))
      })
      .catch(() => undefined)
    return () => { cancelled = true }
  }, [agent.id, loadedReleaseId, hydrateState])

  useEffect(() => {
    if (state.providerModelId || !providerModels?.length || !state.providerCredentialId || !state.model) return
    const providerModel = providerModels.find((item) => item.provider_credential_id === state.providerCredentialId && item.model === state.model)
    if (providerModel) hydrateState((previous) => previous.providerModelId ? previous : { ...previous, providerModelId: providerModel.id })
  }, [state.providerModelId, state.providerCredentialId, state.model, providerModels, hydrateState])

  useEffect(() => {
    if (state.fallbackProviderModelId || !providerModels?.length || !state.fallbackProviderCredentialId || !state.fallbackModel) return
    const providerModel = providerModels.find((item) => item.provider_credential_id === state.fallbackProviderCredentialId && item.model === state.fallbackModel)
    if (providerModel) hydrateState((previous) => previous.fallbackProviderModelId ? previous : { ...previous, fallbackProviderModelId: providerModel.id })
  }, [state.fallbackProviderModelId, state.fallbackProviderCredentialId, state.fallbackModel, providerModels, hydrateState])

  useEffect(() => {
    if (!state.providerModelId || !providerModels?.length) return
    const providerModel = providerModels.find((item) => item.id === state.providerModelId)
    if (!providerModel) return
    const credential = credentials?.find((item) => item.id === providerModel.provider_credential_id)
    hydrateState((previous) => {
      const provider = providerModel.provider || credential?.provider || previous.provider
      const model = providerModel.model || previous.model
      const providerCredentialId = providerModel.provider_credential_id || previous.providerCredentialId
      const baseUrl = credential?.metadata?.base_url || previous.baseUrl
      if (previous.provider === provider && previous.model === model && previous.providerCredentialId === providerCredentialId && previous.baseUrl === baseUrl) return previous
      return { ...previous, provider, model, providerCredentialId, baseUrl }
    })
  }, [state.providerModelId, providerModels, credentials, hydrateState])

  useEffect(() => {
    if (!state.fallbackProviderModelId || !providerModels?.length) return
    const providerModel = providerModels.find((item) => item.id === state.fallbackProviderModelId)
    if (!providerModel) return
    const credential = credentials?.find((item) => item.id === providerModel.provider_credential_id)
    hydrateState((previous) => {
      const fallbackProvider = providerModel.provider || credential?.provider || previous.fallbackProvider
      const fallbackModel = providerModel.model || previous.fallbackModel
      const fallbackProviderCredentialId = providerModel.provider_credential_id || previous.fallbackProviderCredentialId
      if (previous.fallbackProvider === fallbackProvider && previous.fallbackModel === fallbackModel && previous.fallbackProviderCredentialId === fallbackProviderCredentialId) return previous
      return { ...previous, fallbackProvider, fallbackModel, fallbackProviderCredentialId }
    })
  }, [state.fallbackProviderModelId, providerModels, credentials, hydrateState])

  useEffect(() => {
    if (state.providerModelId || !state.providerCredentialId || !credentials?.length) return
    const credential = credentials.find((item) => item.id === state.providerCredentialId)
    if (!credential) return
    hydrateState((previous) => {
      const provider = credential.provider
      const model = credential.metadata?.model || credential.metadata?.model_name || previous.model
      const baseUrl = credential.metadata?.base_url || previous.baseUrl
      if (previous.provider === provider && previous.model === model && previous.baseUrl === baseUrl) return previous
      return { ...previous, provider, model, baseUrl }
    })
  }, [state.providerModelId, state.providerCredentialId, credentials, hydrateState])

  useEffect(() => {
    if (state.fallbackProviderModelId || !state.fallbackProviderCredentialId || !credentials?.length) return
    const credential = credentials.find((item) => item.id === state.fallbackProviderCredentialId)
    if (!credential) return
    hydrateState((previous) => ({ ...previous, fallbackProvider: credential.provider, fallbackModel: credential.metadata?.model || credential.metadata?.model_name || previous.fallbackModel }))
  }, [state.fallbackProviderModelId, state.fallbackProviderCredentialId, credentials, hydrateState])

  const setField = useCallback(<K extends keyof AgentEditorState>(key: K, value: AgentEditorState[K]) => {
    editedFields.current.add(key)
    setEditorState((previous) => ({ ...previous, [key]: value }))
  }, [])

  const setState = useCallback((next: AgentEditorState) => {
    for (const key of Object.keys(next) as Array<keyof AgentEditorState>) editedFields.current.add(key)
    setEditorState(next)
  }, [])

  const setLoadedRelease = useCallback((id: string | null, version: string | null) => { setLoadedReleaseId(id); setLoadedReleaseVersion(version) }, [])
  const toSnapshot = useCallback((): Record<string, unknown> => canonicalSnapshot(state), [state])
  const snapshot = useMemo(() => JSON.stringify(canonicalSnapshot(state)), [state])
  const baselineSnapshot = useMemo(() => JSON.stringify(canonicalSnapshot(baselineState)), [baselineState])
  const isDirty = snapshot !== baselineSnapshot
  const activeSource: 'current_draft' | 'draft_unsaved' = isDirty ? 'draft_unsaved' : 'current_draft'
  const resetToBaseline = useCallback(() => {
    editedFields.current.clear()
    setEditorState(baselineState)
    setLoadedRelease(null, null)
  }, [baselineState, setLoadedRelease])
  const updateBaseline = useCallback((confirmedState: AgentEditorState = state) => {
    setBaselineState(confirmedState)
    setEditorState((current) => {
      const remainingEdits = new Set<keyof AgentEditorState>()
      for (const key of Object.keys(current) as Array<keyof AgentEditorState>) {
        if (!sameEditorValue(current[key], confirmedState[key])) remainingEdits.add(key)
      }
      editedFields.current = remainingEdits
      return current
    })
  }, [state])

  return <EditorContext.Provider value={{ state, setField, setState, toSnapshot, loadedReleaseId, loadedReleaseVersion, setLoadedRelease, isDirty, activeSource, resetToBaseline, updateBaseline }}>{children}</EditorContext.Provider>
}

export function useAgentEditor(): EditorContextValue {
  const context = useContext(EditorContext)
  if (!context) throw new Error('useAgentEditor must be used within AgentEditorProvider')
  return context
}
