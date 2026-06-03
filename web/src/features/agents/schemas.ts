import { z } from 'zod'

export const createAgentSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  description: z.string().optional(),
  provider: z.string().min(1, 'Provider is required'),
  model: z.string().min(1, 'Model is required'),
  system_prompt: z.string().optional(),
  temperature: z.coerce.number().min(0).max(2).optional(),
  max_output_tokens: z.coerce.number().min(1).optional(),
  provider_credential_id: z.string().optional(),
})

export type CreateAgentFormData = z.infer<typeof createAgentSchema>
