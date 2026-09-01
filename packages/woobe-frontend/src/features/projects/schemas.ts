import { z } from 'zod'

export const createProjectSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  slug: z.string().optional(),
})

export type CreateProjectFormData = z.infer<typeof createProjectSchema>
