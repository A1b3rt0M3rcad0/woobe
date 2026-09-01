import { z } from 'zod'

export const createWorkspaceSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  slug: z.string().optional(),
})

export const updateWorkspaceSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  slug: z.string().optional(),
})

export const inviteMemberSchema = z.object({
  email: z.string().email('Invalid email address'),
  role: z.string().default('member'),
})

export type CreateWorkspaceFormData = z.infer<typeof createWorkspaceSchema>
export type UpdateWorkspaceFormData = z.infer<typeof updateWorkspaceSchema>
export type InviteMemberFormData = z.infer<typeof inviteMemberSchema>
