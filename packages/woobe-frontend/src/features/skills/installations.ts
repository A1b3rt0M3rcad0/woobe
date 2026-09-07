import type { Agent } from '@/features/agents/types'
import { record, skillsConfig } from './config'
import type { SkillBinding, SkillSnapshot } from './types'

export interface SavedSkillInstallation {
  agent: Agent
  binding: SkillBinding
  snapshot?: SkillSnapshot
}

/** Saved Agent configuration only; unsaved edits and historical Releases are not installations. */
export function savedSkillInstallations(agents: Agent[], projectId: string): SavedSkillInstallation[] {
  return agents.filter(agent => agent.project_id === projectId).flatMap(agent => {
    const config = skillsConfig(record(agent.settings).runtime_config)
    return config.bindings.map(binding => ({ agent, binding, snapshot: config.snapshots.find(snapshot => snapshot.skill_version_id === binding.skill_version_id) }))
  })
}
