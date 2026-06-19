import { z } from 'zod'

export const apiKeyScopeSchema = z.enum([
  'runtime:execute',
  'traces:read',
  'usage:read',
])

export const createApiKeySchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(255),
  scopes: z.array(apiKeyScopeSchema).min(1, 'Select at least one scope'),
  expires_at: z.string().optional(),
})

export type CreateApiKeyFormData = z.infer<typeof createApiKeySchema>
