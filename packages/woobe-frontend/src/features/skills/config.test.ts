import { describe, expect, it } from 'vitest'
import { canonicalSnapshot, agentToEditorState } from '@/features/playground/AgentEditorContext'
import { enableSkillsContext, installSkill, readSkillFiles, skillsConfig } from './config'
import type { ContextAssemblerDescriptor } from '@/features/agents/types'
import type { SkillSnapshot } from './types'

const manager: ContextAssemblerDescriptor = { name: 'stdcm', version: 'v2', strategy_name: 'stdcm', strategy_version: 'v2', supports_skills: true, display_name: 'Standard v2', description: '', behavior: '', recommended_for: [], capabilities: [], limitations: [], configuration: '', is_default: false, is_system_default_alias: false }
const snapshot: SkillSnapshot = { skill_id: 'skill', skill_version_id: 'version-1', project_id: 'project', version: '1.0.0', package_hash: 'hash', package: { name: 'invoice-review', description: 'Review invoices', instructions: 'Check totals', skill_md: 'Check totals', resources: {}, required_tools: [] } }

describe('Agent Skills configuration', () => {
  it('preserves unrelated configuration and custom context policy when installing', () => {
    const runtime = { output: { strict: true }, context: { session: { max_messages: 12 }, allowed_sources: ['SYSTEM', 'USER_INPUT'] } }
    const installed = installSkill(runtime, snapshot, manager)
    expect(installed.output).toEqual(runtime.output)
    expect(installed.context).toMatchObject({ session: { max_messages: 12 }, allowed_sources: ['SYSTEM', 'USER_INPUT', 'SKILL', 'TOOL'], skills: { max_units: 8000 } })
    expect(runtime).not.toHaveProperty('skills')
  })
  it('replaces a pinned version explicitly without duplicate installation', () => {
    const first = installSkill({}, snapshot, manager)
    const next = installSkill(first, { ...snapshot, skill_version_id: 'version-2', version: '2.0.0' }, manager)
    expect(skillsConfig(next).bindings).toEqual([{ skill_id: 'skill', skill_version_id: 'version-2', enabled: true }])
    expect(skillsConfig(first).snapshots[0].version).toBe('1.0.0')
  })
  it('requires backend-declared support', () => {
    expect(() => enableSkillsContext({}, { ...manager, supports_skills: false })).toThrow('supports Skills')
  })
  it('retains bindings and packages in editor snapshots for save and release', () => {
    const runtime = installSkill({}, snapshot, manager)
    const state = agentToEditorState({ id: 'agent', project_id: 'project', name: 'Agent', model: 'test', provider: 'openai', status: 'active', settings: { runtime_config: runtime } })
    expect(skillsConfig(canonicalSnapshot(state).runtime_config)).toEqual(skillsConfig(runtime))
  })
  it('rejects unsupported package files without silently discarding them', async () => {
    const file = (name: string, path: string) => ({ name, webkitRelativePath: path, size: 8, arrayBuffer: async () => new TextEncoder().encode('contents').buffer }) as File
    await expect(readSkillFiles([file('SKILL.md', 'demo/SKILL.md'), file('run.py', 'demo/scripts/run.py')])).rejects.toThrow('Unsupported file')
    await expect(readSkillFiles([file('SKILL.md', 'demo/SKILL.md'), file('guide.md', 'demo/references/guide.md')])).resolves.toEqual({ skill_md: 'contents', resources: { 'references/guide.md': 'contents' } })
  })
})
