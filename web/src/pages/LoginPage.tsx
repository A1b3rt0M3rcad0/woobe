import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthProvider'
import { loginSchema, type LoginFormData } from '@/features/auth/schemas'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const { register, handleSubmit, formState: { errors, isSubmitting }, setError } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginFormData) => {
    try {
      await login(data)
      navigate('/dashboard')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Login failed'
      setError('root', { message })
    }
  }

  return (
    <div>
      <h2 className="text-xl font-semibold text-white mb-6">Sign in</h2>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Email</label>
          <Input type="email" {...register('email')} error={errors.email?.message} placeholder="you@company.com" />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Password</label>
          <Input type="password" {...register('password')} error={errors.password?.message} placeholder="Enter your password" />
        </div>
        {errors.root && <p className="text-sm text-red-500">{errors.root.message}</p>}
        <Button type="submit" loading={isSubmitting} className="w-full">
          Sign in
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted">
        Don&apos;t have an account?{' '}
        <Link to="/register" className="text-primary hover:underline">Create one</Link>
      </p>
    </div>
  )
}
