export interface Skill { id: string; project_id: string; name: string; created_at: string }
export interface SkillSummary extends Skill {
  latest_version_id: string | null
  latest_version: string | null
  latest_description: string | null
  latest_required_tools: string[]
  latest_estimated_instruction_units: number | null
  latest_resource_count: number
  latest_version_created_at: string | null
  version_count: number
}
export interface SkillVersion {
  id: string; skill_id: string; version: string; name: string; description: string
  package_hash: string; required_tools: string[]; estimated_instruction_units: number
  resource_paths: string[]; created_at: string
}
export interface SkillPackage {
  name: string; description: string; instructions: string; skill_md: string
  resources: Record<string, string>; required_tools: string[]
}
export interface SkillSnapshot {
  skill_id: string; skill_version_id: string; project_id: string; version: string
  package_hash: string; package: SkillPackage
}
export interface SkillBinding { skill_id: string; skill_version_id: string; enabled: boolean }
export interface SkillsConfig { bindings: SkillBinding[]; snapshots: SkillSnapshot[] }
export interface ImportSkill { version: string; skill_md: string; resources: Record<string, string>; required_tools: string[] }
