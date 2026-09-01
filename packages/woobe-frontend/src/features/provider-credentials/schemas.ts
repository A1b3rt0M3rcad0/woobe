import { z } from 'zod'

export const createProviderCredentialSchema = z.object({
  provider: z.string().min(1, 'Provider is required'),
  name: z.string().min(1, 'Name is required'),
  secret: z.string().min(1, 'API key is required'),
})

export type CreateProviderCredentialFormData = z.infer<typeof createProviderCredentialSchema>
