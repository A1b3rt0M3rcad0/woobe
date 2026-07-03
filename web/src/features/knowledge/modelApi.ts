import { get, post } from '@/lib/api/client'
import type { CreateKnowledgeProviderModelRequest, KnowledgeProviderModel } from './types'

export async function getKnowledgeProviderModels(projectId?: string): Promise<KnowledgeProviderModel[]> {
  return get<KnowledgeProviderModel[]>('/ai/provider-models', { params: { project_id: projectId } })
}

export async function createKnowledgeProviderModel(data: CreateKnowledgeProviderModelRequest): Promise<KnowledgeProviderModel> {
  return post<KnowledgeProviderModel>('/ai/provider-models', data)
}
