import type { BehaviorSpecification } from './types'

export interface AgentBehavior {
  objective: string
  responsibilities: string[]
  allowedBehaviors: string[]
  disallowedBehaviors: string[]
  operatingInstructions: string
  responseGuidelines: string
  additionalInstructions: string
}

export const behaviorFields = [
  { key: 'objective', specKey: 'objective', label: 'Objective', help: 'What primary outcome should this Agent achieve?' },
  { key: 'responsibilities', specKey: 'responsibilities', label: 'Responsibilities', help: 'What is this Agent responsible for?' },
  { key: 'allowedBehaviors', specKey: 'allowed_behaviors', label: 'Allowed Behaviors', help: 'Which actions and attitudes are appropriate for this Agent?' },
  { key: 'disallowedBehaviors', specKey: 'disallowed_behaviors', label: 'Disallowed Behaviors', help: 'Which behaviors should this Agent avoid?' },
  { key: 'operatingInstructions', specKey: 'operating_instructions', label: 'Operating Instructions', help: 'How should this Agent perform its work?' },
  { key: 'responseGuidelines', specKey: 'response_guidelines', label: 'Response Guidelines', help: 'How should this Agent communicate results? Configure structured output separately in Output.' },
  { key: 'additionalInstructions', specKey: 'additional_instructions', label: 'Additional Instructions', help: 'Additional guidance, including instructions preserved from an older Agent.' },
] as const

export function behaviorFromSpec(spec?: BehaviorSpecification | null, legacyPrompt = ''): AgentBehavior {
  return {
    objective: spec?.objective ?? '',
    responsibilities: [...(spec?.responsibilities ?? [])],
    allowedBehaviors: [...(spec?.allowed_behaviors ?? [])],
    disallowedBehaviors: [...(spec?.disallowed_behaviors ?? [])],
    operatingInstructions: spec?.operating_instructions ?? '',
    responseGuidelines: spec?.response_guidelines ?? '',
    additionalInstructions: spec ? spec.additional_instructions ?? '' : legacyPrompt,
  }
}

export function behaviorToSpec(behavior: AgentBehavior): BehaviorSpecification {
  const items = (values: string[]) => values.map(value => value.trim()).filter(Boolean)
  return {
    schema_version: 1,
    objective: behavior.objective,
    responsibilities: items(behavior.responsibilities),
    allowed_behaviors: items(behavior.allowedBehaviors),
    disallowed_behaviors: items(behavior.disallowedBehaviors),
    operating_instructions: behavior.operatingInstructions,
    response_guidelines: behavior.responseGuidelines,
    additional_instructions: behavior.additionalInstructions,
  }
}
