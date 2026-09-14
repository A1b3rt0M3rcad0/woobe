import { useQuery } from '@tanstack/react-query'

import { get } from '@/lib/api/client'

export interface RagStrategyDescriptor {
  name: string
  display_name: string
  description: string
  is_default: boolean
}

export async function getRagStrategies(): Promise<RagStrategyDescriptor[]> {
  return get<RagStrategyDescriptor[]>('/ai/rag-strategies')
}

export function useRagStrategies() {
  return useQuery({
    queryKey: ['rag-strategies'],
    queryFn: getRagStrategies,
    staleTime: Infinity,
  })
}
