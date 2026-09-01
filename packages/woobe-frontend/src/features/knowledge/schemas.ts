import { z } from 'zod'

export const createCollectionSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  description: z.string().optional(),
})

export type CreateCollectionFormData = z.infer<typeof createCollectionSchema>

export const updateCollectionSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  description: z.string().optional(),
})

export type UpdateCollectionFormData = z.infer<typeof updateCollectionSchema>
