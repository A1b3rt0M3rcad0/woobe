import { z } from 'zod'

export const createToolSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  description: z.string().optional(),
  type: z.string().min(1, 'Type is required'),
  config: z.string().optional(),
  input_schema: z.string().optional(),
  output_schema: z.string().optional(),
  risk_level: z.string().optional(),
  timeout_ms: z.coerce.number().optional(),
})

export type CreateToolFormData = z.infer<typeof createToolSchema>

export const createSecretSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  type: z.string().optional(),
  value: z.string().min(1, 'Value is required'),
})

export type CreateSecretFormData = z.infer<typeof createSecretSchema>
