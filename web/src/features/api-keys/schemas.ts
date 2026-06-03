import { z } from 'zod'

export const createApiKeySchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
})

export type CreateApiKeyFormData = z.infer<typeof createApiKeySchema>
