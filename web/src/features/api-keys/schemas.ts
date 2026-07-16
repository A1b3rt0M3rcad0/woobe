import { z } from 'zod'

export const apiKeyScopeSchema = z.enum([
  'runtime:execute',
  'traces:read',
  'usage:read',
])

export const runtimeInterfaceSchema = z.enum(['http', 'stream', 'jobs'])

export const createApiKeySchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(255),
  description: z.string().trim().max(500).optional(),
  scopes: z.array(apiKeyScopeSchema).min(1, 'Select at least one scope'),
  expires_at: z.string().optional(),
})

export const createRuntimeApiKeySchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(255),
  description: z.string().trim().max(500).optional(),
  interfaces: z.array(runtimeInterfaceSchema).min(1, 'Select at least one interface'),
})

export type CreateApiKeyFormData = z.infer<typeof createApiKeySchema>
export type CreateRuntimeApiKeyFormData = z.infer<typeof createRuntimeApiKeySchema>
