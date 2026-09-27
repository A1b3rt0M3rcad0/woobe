import type { ContextManagerDescriptor } from '@/features/agents/types'
import type { SkillSnapshot, SkillsConfig } from './types'

export const record = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
export function skillsConfig(runtime: unknown): SkillsConfig {
  const raw = record(record(runtime).skills)
  return {
    bindings: Array.isArray(raw.bindings) ? raw.bindings : [],
    snapshots: Array.isArray(raw.snapshots) ? raw.snapshots : [],
  }
}
export function enableSkillsContext(runtime: Record<string, unknown>, manager: ContextManagerDescriptor): Record<string, unknown> {
  if (!manager.supports_skills) throw new Error('Choose a Context Manager that supports Skills.')
  const context = record(runtime.context)
  const sources = Array.isArray(context.allowed_sources) ? context.allowed_sources : ['SYSTEM', 'USER_INPUT', 'SESSION', 'KNOWLEDGE', 'TOOL', 'DELEGATION', 'RUNTIME']
  const nextRuntime = { ...runtime }
  delete nextRuntime.context_assembler
  return {
    ...nextRuntime,
    context_manager: { name: manager.name },
    context: { ...context, allowed_sources: [...new Set([...sources, 'SKILL', 'TOOL'])],
      source_priorities: { ...record(context.source_priorities), SKILL: 'MANDATORY' },
      skills: { max_units: 8000, catalog_max_units: 2000, search_limit: 8, ...record(context.skills) } },
  }
}
export function installSkill(runtime: Record<string, unknown>, snapshot: SkillSnapshot, manager: ContextManagerDescriptor): Record<string, unknown> {
  const config = skillsConfig(runtime)
  return { ...enableSkillsContext(runtime, manager), skills: {
    bindings: [...config.bindings.filter(item => item.skill_id !== snapshot.skill_id), { skill_id: snapshot.skill_id, skill_version_id: snapshot.skill_version_id, enabled: true }],
    snapshots: [...config.snapshots.filter(item => item.skill_id !== snapshot.skill_id), snapshot],
  } }
}

export async function readSkillFiles(files: File[]): Promise<{ skill_md: string; resources: Record<string, string> }> {
  if (!files.length || files.length > 65) throw new Error('Select SKILL.md and up to 64 text resources.')
  if (files.reduce((sum, file) => sum + file.size, 0) > 1_000_000) throw new Error('Skill packages must be at most 1 MB.')
  const paths = files.map(file => file.webkitRelativePath || file.name)
  const manifests = paths.filter(path => path === 'SKILL.md' || path.endsWith('/SKILL.md'))
  if (manifests.length !== 1) throw new Error('Select a package containing exactly one SKILL.md.')
  const prefix = manifests[0].slice(0, -'SKILL.md'.length)
  const resources: Record<string, string> = {}
  let skill_md = ''
  for (let index = 0; index < files.length; index++) {
    const path = paths[index]
    if (!path.startsWith(prefix)) throw new Error('All files must be inside the Skill package.')
    const relative = path.slice(prefix.length)
    if (files[index].size > 200_000) throw new Error(`${relative} exceeds 200 KB.`)
    if (relative !== 'SKILL.md' && (!/^(references|assets)\/.+\.(md|txt|json|yaml|yml|csv)$/i.test(relative) || relative.split('/').some(part => !part || part === '.' || part === '..') || relative.includes('\\'))) throw new Error(`Unsupported file: ${relative}. This version supports text resources in references/ and assets/.`)
    const content = new TextDecoder('utf-8', { fatal: true }).decode(await files[index].arrayBuffer())
    if (content.includes('\0')) throw new Error(`${relative} is not a supported text file.`)
    if (relative === 'SKILL.md') skill_md = content
    else {
      if (relative in resources) throw new Error(`Duplicate resource: ${relative}`)
      resources[relative] = content
    }
  }
  return { skill_md, resources }
}
