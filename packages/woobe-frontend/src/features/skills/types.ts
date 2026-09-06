export interface Skill { id: string; project_id: string; name: string; created_at: string }
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
