import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthProvider'
import { registerSchema, type RegisterFormData } from '@/features/auth/schemas'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

export default function RegisterPage() {
  const { register: registerUser } = useAuth()
  const navigate = useNavigate()
  const { register, handleSubmit, formState: { errors, isSubmitting }, setError } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  })

  const onSubmit = async (data: RegisterFormData) => {
    try {
      await registerUser(data)
      navigate('/dashboard')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Registration failed'
      setError('root', { message })
    }
  }

  return (
    <div>
      <h2 className="text-xl font-semibold text-white mb-6">Create account</h2>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Email</label>
          <Input type="email" {...register('email')} error={errors.email?.message} placeholder="you@company.com" />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Password</label>
          <Input type="password" {...register('password')} error={errors.password?.message} placeholder="At least 6 characters" />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Organization</label>
          <Input {...register('organization_name')} error={errors.organization_name?.message} placeholder="Your company name" />
        </div>
        {errors.root && <p className="text-sm text-red-500">{errors.root.message}</p>}
        <Button type="submit" loading={isSubmitting} className="w-full">
          Create account
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted">
        Already have an account?{' '}
        <Link to="/login" className="text-primary hover:underline">Sign in</Link>
      </p>
    </div>
  )
}
