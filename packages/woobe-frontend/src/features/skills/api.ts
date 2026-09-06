import { get, post } from '@/lib/api/client'
import type { ImportSkill, Skill, SkillSnapshot, SkillVersion } from './types'
const root = (projectId: string) => `/ai/projects/${projectId}/skills`
export const listSkills = (projectId: string, query: string, offset: number) => get<Skill[]>(root(projectId), { params: { query, offset, limit: 20 } })
export const listSkillVersions = (projectId: string, skillId: string, offset: number) => get<SkillVersion[]>(`${root(projectId)}/${skillId}/versions`, { params: { offset, limit: 20 } })
export const getSkillVersion = (projectId: string, versionId: string) => get<SkillVersion & SkillSnapshot>(`${root(projectId)}/versions/${versionId}`)
export const importSkill = (projectId: string, input: ImportSkill, skillId?: string) => post<SkillVersion & SkillSnapshot>(skillId ? `${root(projectId)}/${skillId}/versions` : root(projectId), input)
