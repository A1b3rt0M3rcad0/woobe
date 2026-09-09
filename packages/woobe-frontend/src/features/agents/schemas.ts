import { z } from 'zod'

export const createAgentSchema = z.object({
  name: z.string().min(1, 'Agent name is required').max(255),
  description: z.string().optional(),
  provider: z.string().optional(),
  model: z.string().optional(),
  objective: z.string().optional(),
  temperature: z.coerce.number().min(0).max(2).optional(),
  max_output_tokens: z.coerce.number().min(1).optional(),
  provider_credential_id: z.string().optional(),
  session_mode: z.enum(['stateful', 'stateless']).default('stateful'),
  status: z.enum(['active', 'inactive']).default('active'),
}).superRefine((data, ctx) => {
  if (data.provider && data.provider !== 'custom') {
    if (!data.model) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['model'],
        message: 'Select a model to continue.',
      })
    }
  }
})

export type CreateAgentFormData = z.infer<typeof createAgentSchema>
