import { get } from '@/lib/api/client'
import type { KnowledgeProviderModel } from './types'

export async function getKnowledgeProviderModels(projectId?: string): Promise<KnowledgeProviderModel[]> {
  return get<KnowledgeProviderModel[]>('/ai/provider-models', { params: { project_id: projectId } })
}
