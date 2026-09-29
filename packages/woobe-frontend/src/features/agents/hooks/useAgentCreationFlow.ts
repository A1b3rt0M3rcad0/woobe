import { behaviorFromSpec, behaviorToSpec } from '@/features/agents/behavior'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { useCreateAgent } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { useCredentials } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { modelProviderLabel, MODEL_PROVIDER_OPTIONS } from '@/features/provider-credentials/providers'
import {
  useAvailableProviderModels,
  useCreateProviderModel,
  useProviderModels,
} from '@/features/provider-models/hooks'
import type { AvailableProviderModel, ProviderModel } from '@/features/provider-models/types'

export type AgentCreationStep = 'details' | 'model' | 'review'
export type ModelSelectionMode = 'existing' | 'catalog' | 'manual'

interface UseAgentCreationFlowOptions {
  projectId: string
  onCreated: (agent: Agent) => void
  active?: boolean
}

const supportedProviders = new Set(MODEL_PROVIDER_OPTIONS.map((provider) => provider.value))

export const providerLabel = modelProviderLabel

export function supportsModelCatalog(credential?: ProviderCredential | null) {
  return Boolean(credential && supportedProviders.has(credential.provider))
}

export function isEmbeddingProviderModel(model: ProviderModel) {
  if (model.model_type) return model.model_type === 'embedding'
  if (Array.isArray(model.spec?.operations) && model.spec.operations.includes('embedding.create')) return true
  const metadata = model.metadata || {}
  const capability = String(metadata.capability || metadata.type || '').trim().toLowerCase()
  if (capability) return capability === 'embedding' || capability === 'embeddings'
  return `${model.name} ${model.model}`.toLowerCase().includes('embed')
}

export function buildModelMetadata(catalogModel: AvailableProviderModel | null) {
  if (!catalogModel) {
    return {
      capability: 'generation',
      source: 'manual',
      pricing: {
        input_cost_per_1m_tokens: null,
        output_cost_per_1m_tokens: null,
        currency: 'USD',
        billing_unit: 'per_1m_tokens',
        source: 'manual',
      },
    }
  }

  return {
    capability: catalogModel.model_type || 'generation',
    source: 'remote',
    catalog: {
      provider: catalogModel.provider,
      model_id: catalogModel.id,
      label: catalogModel.label,
      owned_by: catalogModel.owned_by ?? null,
      model_type: catalogModel.model_type ?? null,
      operations: catalogModel.operations ?? [],
      input_modalities: catalogModel.input_modalities ?? [],
      output_modalities: catalogModel.output_modalities ?? [],
      context_window: catalogModel.context_window ?? null,
    },
    capabilities: {
      supports_tools: catalogModel.supports_tools ?? null,
      supports_json: catalogModel.supports_json ?? null,
      supports_streaming: catalogModel.supports_streaming ?? null,
    },
    pricing: {
      input_cost_per_1m_tokens: catalogModel.input_cost_per_1m_tokens ?? null,
      output_cost_per_1m_tokens: catalogModel.output_cost_per_1m_tokens ?? null,
      currency: 'USD',
      billing_unit: 'per_1m_tokens',
      source: 'provider_catalog',
    },
    provider_model_raw: catalogModel.raw,
  }
}

export function useAgentCreationFlow({ projectId, onCreated, active = true }: UseAgentCreationFlowOptions) {
  const credentialsQuery = useCredentials(projectId)
  const modelsQuery = useProviderModels(projectId)
  const createModel = useCreateProviderModel()
  const createAgent = useCreateAgent(projectId)

  const [step, setStep] = useState<AgentCreationStep>('details')
  const [agentName, setAgentName] = useState('')
  const [agentDescription, setAgentDescription] = useState('')
  const [agentObjective, setAgentObjective] = useState('')
  const [modelMode, setModelMode] = useState<ModelSelectionMode>('existing')
  const [selectedCredentialId, setSelectedCredentialId] = useState('')
  const [selectedModelId, setSelectedModelId] = useState('')
  const [selectedCatalogModelId, setSelectedCatalogModelId] = useState('')
  const [manualModelIdentifier, setManualModelIdentifier] = useState('')
  const [manualModelName, setManualModelName] = useState('')
  const [createdCredential, setCreatedCredential] = useState<ProviderCredential | null>(null)
  const [createdModel, setCreatedModel] = useState<ProviderModel | null>(null)

  const resetFlow = () => {
    setStep('details')
    setAgentName('')
    setAgentDescription('')
    setAgentObjective('')
    setModelMode('existing')
    setSelectedCredentialId('')
    setSelectedModelId('')
    setSelectedCatalogModelId('')
    setManualModelIdentifier('')
    setManualModelName('')
    setCreatedCredential(null)
    setCreatedModel(null)
  }

  useEffect(() => {
    if (!active) return
    resetFlow()
  }, [active, projectId])

  const credentials = useMemo(() => {
    const source = credentialsQuery.data ?? []
    if (!createdCredential || source.some((item) => item.id === createdCredential.id)) return source
    return [...source, createdCredential]
  }, [credentialsQuery.data, createdCredential])

  const activeCredentials = useMemo(
    () => credentials.filter((credential) => (
      (!credential.status || credential.status === 'active')
      && supportedProviders.has(credential.provider)
    )),
    [credentials],
  )

  const activeCredentialIds = useMemo(
    () => new Set(activeCredentials.map((credential) => credential.id)),
    [activeCredentials],
  )

  const models = useMemo(() => {
    const source = modelsQuery.data ?? []
    if (!createdModel || source.some((item) => item.id === createdModel.id)) return source
    return [...source, createdModel]
  }, [modelsQuery.data, createdModel])

  const usableAgentModels = useMemo(
    () => models.filter((model) => (
      model.status === 'active'
      && activeCredentialIds.has(model.provider_credential_id)
      && !isEmbeddingProviderModel(model)
    )),
    [models, activeCredentialIds],
  )

  const selectedCredential = activeCredentials.find((item) => item.id === selectedCredentialId) || null
  const selectedModel = usableAgentModels.find((item) => item.id === selectedModelId) || null
  const canUseCatalog = supportsModelCatalog(selectedCredential)
  const shouldLoadCatalog = active && step === 'model' && modelMode === 'catalog' && canUseCatalog

  const availableModelsQuery = useAvailableProviderModels(
    projectId,
    shouldLoadCatalog ? selectedCredentialId : undefined,
    'generation',
  )
  const availableModels = availableModelsQuery.data ?? []
  const selectedCatalogModel = availableModels.find((item) => item.id === selectedCatalogModelId) || null

  useEffect(() => {
    if (!active || selectedCredentialId || activeCredentials.length !== 1) return
    setSelectedCredentialId(activeCredentials[0].id)
  }, [active, activeCredentials, selectedCredentialId])

  const chooseModeForCredential = (credential: ProviderCredential | null) => {
    setModelMode(supportsModelCatalog(credential) ? 'catalog' : 'manual')
    setSelectedCatalogModelId('')
    setManualModelIdentifier('')
    setManualModelName('')
  }

  const continueFromDetails = () => {
    if (!agentName.trim()) {
      toast.error('Agent name is required')
      return false
    }
    if (!agentObjective.trim()) {
      toast.error('Agent objective is required')
      return false
    }

    if (usableAgentModels.length > 0) {
      setModelMode('existing')
    } else {
      const credential = selectedCredential || activeCredentials[0] || null
      if (credential && !selectedCredentialId) setSelectedCredentialId(credential.id)
      chooseModeForCredential(credential)
    }
    setStep('model')
    return true
  }

  const showExistingModels = () => {
    setModelMode('existing')
  }

  const startNewModel = () => {
    const credential = selectedCredential || activeCredentials[0] || null
    if (credential && !selectedCredentialId) setSelectedCredentialId(credential.id)
    chooseModeForCredential(credential)
  }

  const selectCredential = (credentialId: string) => {
    const credential = activeCredentials.find((item) => item.id === credentialId) || null
    setSelectedCredentialId(credentialId)
    chooseModeForCredential(credential)
  }

  const registerCreatedCredential = (credential: ProviderCredential) => {
    setCreatedCredential(credential)
    setSelectedCredentialId(credential.id)
    chooseModeForCredential(credential)
  }

  const selectExistingModel = (modelId: string) => {
    setSelectedModelId(modelId)
    setModelMode('existing')
  }

  const selectCatalogModel = (model: AvailableProviderModel) => {
    setSelectedCatalogModelId(model.id)
    setManualModelIdentifier(model.id)
    setManualModelName(model.label || model.id)
    setModelMode('catalog')
  }

  const useCatalogMode = () => {
    if (!selectedCredential || !supportsModelCatalog(selectedCredential)) return
    setModelMode('catalog')
    setSelectedCatalogModelId('')
    setManualModelIdentifier('')
    setManualModelName('')
  }

  const setManualModel = (identifier: string, name?: string) => {
    setSelectedCatalogModelId('')
    setManualModelIdentifier(identifier)
    setManualModelName(name || '')
    setModelMode('manual')
  }

  const continueFromModel = async () => {
    if (modelMode === 'existing') {
      if (!selectedModel) {
        toast.error('Select a model')
        return false
      }
      setStep('review')
      return true
    }

    if (!selectedCredential) {
      toast.error('Connect or select a provider first')
      return false
    }

    const resolvedModel = manualModelIdentifier.trim()
    const resolvedName = manualModelName.trim() || selectedCatalogModel?.label || resolvedModel
    if (!resolvedModel) {
      toast.error('Select or enter a model')
      return false
    }

    try {
      const catalogModel = modelMode === 'catalog' ? selectedCatalogModel : null
      const selectedSpec = catalogModel?.raw?.woobe_model_spec
      const model = await createModel.mutateAsync({
        project_id: projectId,
        provider_credential_id: selectedCredential.id,
        name: resolvedName,
        model: resolvedModel,
        model_type: catalogModel?.model_type || undefined,
        spec: selectedSpec && typeof selectedSpec === 'object'
          ? selectedSpec as Record<string, any>
          : undefined,
        metadata: buildModelMetadata(catalogModel),
      })
      setCreatedModel(model)
      setSelectedModelId(model.id)
      setStep('review')
      toast.success('Model added')
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to add model')
      return false
    }
  }

  const goBack = () => {
    if (step === 'review') {
      setStep('model')
      return
    }
    if (step === 'model') setStep('details')
  }

  const createAgentFromFlow = async () => {
    if (!agentName.trim()) return toast.error('Agent name is required')
    if (!agentObjective.trim()) return toast.error('Agent objective is required')
    if (!selectedModel) return toast.error('Select a generation model')

    try {
      const agent = await createAgent.mutateAsync({
        project_id: projectId,
        name: agentName.trim(),
        description: agentDescription.trim(),
        provider_model_id: selectedModel.id,
        provider: selectedModel.provider || 'openai',
        model: selectedModel.model,
        behavior_spec: behaviorToSpec({ ...behaviorFromSpec(), objective: agentObjective.trim() }),
        temperature: 0.7,
        max_output_tokens: 2048,
        provider_credential_id: selectedModel.provider_credential_id,
        session_mode: 'stateful',
      })
      toast.success('Agent created')
      onCreated(agent)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create agent')
    }
  }

  const canContinueModel = modelMode === 'existing'
    ? Boolean(selectedModel)
    : Boolean(selectedCredential && manualModelIdentifier.trim())

  return {
    step,
    setStep,
    stepNumber: step === 'details' ? 1 : step === 'model' ? 2 : 3,
    agentName,
    setAgentName,
    agentDescription,
    setAgentDescription,
    agentObjective,
    setAgentObjective,
    modelMode,
    credentials,
    activeCredentials,
    selectedCredential,
    selectCredential,
    registerCreatedCredential,
    usableAgentModels,
    selectedModel,
    selectExistingModel,
    availableModels,
    selectedCatalogModel,
    selectCatalogModel,
    manualModelIdentifier,
    manualModelName,
    setManualModel,
    showExistingModels,
    startNewModel,
    useCatalogMode,
    continueFromDetails,
    continueFromModel,
    goBack,
    createAgent: createAgentFromFlow,
    resetFlow,
    inventoryLoading: credentialsQuery.isLoading || modelsQuery.isLoading,
    inventoryError: credentialsQuery.isError || modelsQuery.isError,
    catalogLoading: availableModelsQuery.isLoading,
    catalogError: availableModelsQuery.isError,
    retryInventory: () => {
      void credentialsQuery.refetch()
      void modelsQuery.refetch()
    },
    retryCatalog: () => { void availableModelsQuery.refetch() },
    canUseCatalog,
    canContinueModel,
    busy: createModel.isPending || createAgent.isPending,
    creatingModel: createModel.isPending,
    creatingAgent: createAgent.isPending,
  }
}

export type AgentCreationFlowController = ReturnType<typeof useAgentCreationFlow>
