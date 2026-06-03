import { z } from 'zod'

export const createOrganizationSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  slug: z.string().optional(),
})

export const updateOrganizationSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  slug: z.string().optional(),
})

export const inviteMemberSchema = z.object({
  email: z.string().email('Invalid email address'),
  role: z.string().default('member'),
})

export type CreateOrganizationFormData = z.infer<typeof createOrganizationSchema>
export type UpdateOrganizationFormData = z.infer<typeof updateOrganizationSchema>
export type InviteMemberFormData = z.infer<typeof inviteMemberSchema>
