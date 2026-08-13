import { z } from 'zod'

export const createWorkspaceSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  slug: z.string().max(128).optional(),
})

export type CreateWorkspaceFormData = z.infer<typeof createWorkspaceSchema>
