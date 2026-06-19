import { createContext, useContext, useState, useCallback, useEffect, useMemo, type ReactNode } from 'react'
import type { Agent } from '@/features/agents/types'
import { useCredentials } from '@/features/provider-credentials/hooks'

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
  providerCredentialId: string | null
  fallbackProvider: string
  fallbackModel: string
  fallbackProviderCredentialId: string | null
  baseUrl: string | null
  temperature: number
  maxOutputTokens: number
  sessionMode: 'stateful' | 'stateless'
  status: 'active' | 'inactive'
  collectionIds: string[]
  runtimeConfig: Record<string, unknown>
}

export interface EditorContextValue {
  state: AgentEditorState
  setField: <K extends keyof AgentEditorState>(key: K, value: AgentEditorState[K]) => void
  setState: (s: AgentEditorState) => void
  toSnapshot: () => Record<string, unknown>
  loadedReleaseId: string | null
  loadedReleaseVersion: string | null
  setLoadedRelease: (id: string | null, version: string | null) => void
  isDirty: boolean
  activeSource: 'current_draft' | 'draft_unsaved'
  resetToBaseline: () => void
  updateBaseline: () => void
}

const defaultResponseFormat: ResponseFormat = {
  enabled: false,
  type: 'text',
  strict: false,
  schema: null,
}

export function agentToEditorState(agent: Agent, collectionIds?: string[]): AgentEditorState {
  const settings = (agent.settings || {}) as Record<string, unknown>
  const rf = (settings.response_format as Record<string, unknown>) || {}
  return {
    name: agent.name || '',
    description: agent.description || '',
    systemPrompt: agent.system_prompt || '',
    responseFormat: {
      enabled: Boolean(rf.enabled && rf.type === 'json'),
      type: rf.type === 'json' ? 'json' : 'text',
      strict: Boolean(rf.strict),
      schema: rf.schema ?? null,
      repair_attempts: (rf.repair_attempts as number) ?? undefined,
    },
    outputSchema: rf.schema ?? null,
    provider: agent.provider || '',
    model: agent.model || '',
    providerCredentialId: agent.provider_credential_id || null,
    fallbackProvider: agent.fallback_provider || '',
    fallbackModel: agent.fallback_model || '',
    fallbackProviderCredentialId: agent.fallback_credential_id || null,
    baseUrl: (settings.base_url as string) || null,
    temperature: agent.temperature ?? 0.7,
    maxOutputTokens: agent.max_output_tokens ?? 2048,
    sessionMode: (agent.session_mode as 'stateful' | 'stateless') || 'stateful',
    status: (agent.status as 'active' | 'inactive') || 'active',
    collectionIds: collectionIds || [],
    runtimeConfig: {},
  }
}

export function canonicalSnapshot(state: AgentEditorState): Record<string, unknown> {
  let schema = state.responseFormat.schema
  if (typeof schema === 'string') {
    try {
      schema = JSON.parse(schema as string)
    } catch {
      schema = null
    }
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
    provider: state.provider,
    model: state.model,
    provider_credential_id: state.providerCredentialId,
    fallback_provider: state.fallbackProvider || undefined,
    fallback_model: state.fallbackModel || undefined,
    fallback_credential_id: state.fallbackProviderCredentialId || undefined,
    base_url: state.baseUrl,
    temperature: state.temperature,
    max_output_tokens: state.maxOutputTokens,
    agent_status: state.status,
    collection_ids: state.collectionIds,
    runtime_config: state.runtimeConfig,
  }
}

const EditorContext = createContext<EditorContextValue | null>(null)

export function AgentEditorProvider({ agent, projectId, collectionIds: propCollectionIds, children }: { agent: Agent; projectId?: string; collectionIds?: string[]; children: ReactNode }) {
  const initial = () => agentToEditorState(agent, propCollectionIds)
  const [state, setState] = useState<AgentEditorState>(initial)
  const [baselineState, setBaselineState] = useState<AgentEditorState>(initial)
  const [loadedReleaseId, setLoadedReleaseId] = useState<string | null>(null)
  const [loadedReleaseVersion, setLoadedReleaseVersion] = useState<string | null>(null)
  const { data: credentials } = useCredentials(projectId || '')

  useEffect(() => {
    const next = agentToEditorState(agent, propCollectionIds)
    setState(next)
    setBaselineState(next)
  }, [agent, propCollectionIds])

  useEffect(() => {
    if (!state.providerCredentialId || !credentials?.length) return
    const credential = credentials.find((item: { id: string }) => item.id === state.providerCredentialId)
    if (!credential) return
    setState((previous) => {
      const provider = credential.provider
      const model = credential.metadata?.model || credential.metadata?.model_name || previous.model
      const baseUrl = credential.metadata?.base_url || previous.baseUrl
      if (previous.provider === provider && previous.model === model && previous.baseUrl === baseUrl) {
        return previous
      }
      return { ...previous, provider, model, baseUrl }
    })
  }, [state.providerCredentialId, credentials])

  useEffect(() => {
    if (!state.fallbackProviderCredentialId || !credentials?.length) return
    const credential = credentials.find((item: { id: string }) => item.id === state.fallbackProviderCredentialId)
    if (!credential) return
    setState((previous) => ({
      ...previous,
      fallbackProvider: credential.provider,
      fallbackModel: credential.metadata?.model || credential.metadata?.model_name || previous.fallbackModel,
    }))
  }, [state.fallbackProviderCredentialId, credentials])

  const setField = useCallback(<K extends keyof AgentEditorState>(key: K, value: AgentEditorState[K]) => {
    setState((previous) => ({ ...previous, [key]: value }))
  }, [])

  const setLoadedRelease = useCallback((id: string | null, version: string | null) => {
    setLoadedReleaseId(id)
    setLoadedReleaseVersion(version)
  }, [])

  const toSnapshot = useCallback((): Record<string, unknown> => canonicalSnapshot(state), [state])
  const snapshot = useMemo(() => JSON.stringify(canonicalSnapshot(state)), [state])
  const baselineSnapshot = useMemo(() => JSON.stringify(canonicalSnapshot(baselineState)), [baselineState])
  const isDirty = snapshot !== baselineSnapshot
  const activeSource: 'current_draft' | 'draft_unsaved' = isDirty ? 'draft_unsaved' : 'current_draft'

  const resetToBaseline = useCallback(() => {
    setState(baselineState)
    setLoadedRelease(null, null)
  }, [baselineState, setLoadedRelease])

  const updateBaseline = useCallback(() => setBaselineState(state), [state])

  const contextValue: EditorContextValue = {
    state,
    setField,
    setState,
    toSnapshot,
    loadedReleaseId,
    loadedReleaseVersion,
    setLoadedRelease,
    isDirty,
    activeSource,
    resetToBaseline,
    updateBaseline,
  }

  return <EditorContext.Provider value={contextValue}>{children}</EditorContext.Provider>
}

export function useAgentEditor(): EditorContextValue {
  const context = useContext(EditorContext)
  if (!context) throw new Error('useAgentEditor must be used within AgentEditorProvider')
  return context
}
