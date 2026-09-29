import type { ExecutionStrategyDescriptor } from './types'
import type { ProviderModel } from '@/features/provider-models/types'
import {
  modelCapabilityState,
  providerModelSpec,
  type NormalizedFrontendModelSpec,
} from '@/features/provider-models/modelSpec'

export interface StrategyCompatibilityIssue {
  code: string
  message: string
  severity: 'error' | 'warning'
}

export interface StrategyCompatibilityResult {
  compatible: boolean
  known: boolean
  issues: StrategyCompatibilityIssue[]
}

export interface StrategyRuntimeState {
  toolsEnabled?: boolean
  contextEnabled?: boolean
  knowledgeEnabled?: boolean
}

function intersects(left: string[], right: string[] | null | undefined) {
  if (!right) return true
  const allowed = new Set(right)
  return left.some((item) => allowed.has(item))
}

function capabilityIssue(
  spec: NormalizedFrontendModelSpec,
  capability: string,
  component: string,
): StrategyCompatibilityIssue | null {
  const supported = modelCapabilityState(spec, capability)
  if (supported === true) return null
  if (supported == null && (spec.source === 'legacy' || spec.source === 'manual')) {
    return {
      code: 'model_capability_unknown',
      message: `${component} requires ${capability}, but this legacy/manual ModelSpec does not declare it. The backend will validate at runtime.`,
      severity: 'warning',
    }
  }
  return {
    code: 'model_capability_not_supported',
    message: `${component} requires model capability ${capability}.`,
    severity: 'error',
  }
}

function componentModeIssue(
  component: 'tools' | 'context' | 'knowledge',
  mode: 'required' | 'optional' | 'unsupported',
  enabled: boolean | undefined,
): StrategyCompatibilityIssue | null {
  if (enabled === undefined) return null
  if (mode === 'required' && !enabled) {
    return {
      code: `${component}_required`,
      message: `This strategy requires ${component} to be enabled.`,
      severity: 'error',
    }
  }
  if (mode === 'unsupported' && enabled) {
    return {
      code: `${component}_not_supported`,
      message: `This strategy does not support ${component}.`,
      severity: 'error',
    }
  }
  return null
}

export function executionStrategyCompatibilityForModel(
  model: ProviderModel | null | undefined,
  strategy: ExecutionStrategyDescriptor,
  runtime: StrategyRuntimeState = {},
): StrategyCompatibilityResult {
  const spec = providerModelSpec(model)
  if (!spec) {
    return {
      compatible: true,
      known: false,
      issues: [{
        code: 'model_spec_unavailable',
        message: 'This model has no normalized ModelSpec yet. The backend remains the compatibility authority.',
        severity: 'warning',
      }],
    }
  }

  const compatibility = strategy.compatibility
  const issues: StrategyCompatibilityIssue[] = []

  if (!intersects(spec.operations, compatibility.operations)) {
    issues.push({
      code: 'operation_not_supported',
      message: `Requires one of [${compatibility.operations.join(', ')}], model exposes [${spec.operations.join(', ')}].`,
      severity: 'error',
    })
  }

  if (compatibility.requires_conversation && spec.interaction.supportsConversation !== true) {
    issues.push({
      code: 'conversation_not_supported',
      message: `Requires conversational interaction; model interaction mode is ${spec.interaction.mode || 'unknown'}.`,
      severity: 'error',
    })
  }

  if (!intersects(spec.inputModalities, compatibility.allowed_input_modalities)) {
    issues.push({
      code: 'execution_input_modality_not_supported',
      message: `Input modalities do not overlap: strategy [${compatibility.allowed_input_modalities?.join(', ')}], model [${spec.inputModalities.join(', ')}].`,
      severity: 'error',
    })
  }

  if (!intersects(spec.outputModalities, compatibility.allowed_output_modalities)) {
    issues.push({
      code: 'execution_output_modality_not_supported',
      message: `Output modalities do not overlap: strategy [${compatibility.allowed_output_modalities?.join(', ')}], model [${spec.outputModalities.join(', ')}].`,
      severity: 'error',
    })
  }

  for (const capability of compatibility.required_capabilities) {
    const issue = capabilityIssue(spec, capability, 'Execution strategy')
    if (issue) issues.push(issue)
  }

  for (const [component, mode, enabled] of [
    ['tools', compatibility.tools_mode, runtime.toolsEnabled],
    ['context', compatibility.context_mode, runtime.contextEnabled],
    ['knowledge', compatibility.knowledge_mode, runtime.knowledgeEnabled],
  ] as const) {
    const issue = componentModeIssue(component, mode, enabled)
    if (issue) issues.push(issue)
  }

  if (runtime.toolsEnabled) {
    const issue = capabilityIssue(spec, 'tool_calling', 'Enabled tools')
    if (issue) issues.push(issue)
  }

  return {
    compatible: !issues.some((issue) => issue.severity === 'error'),
    known: true,
    issues,
  }
}
