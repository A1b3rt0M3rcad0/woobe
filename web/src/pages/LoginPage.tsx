import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowRight, LockKeyhole } from 'lucide-react'
import { useAuth } from '@/features/auth/AuthProvider'
import { loginSchema, type LoginFormData } from '@/features/auth/schemas'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

export default function LoginPage() {
  const { login } = useAuth()
  const { register, handleSubmit, formState: { errors, isSubmitting }, setError } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginFormData) => {
    try {
      await login(data)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Login failed'
      setError('root', { message })
    }
  }

  return (
    <div>
      <div className="mb-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-background/60 px-2.5 py-1 text-[11px] font-medium text-muted">
          <LockKeyhole className="h-3 w-3 text-primary-light" />
          Control plane access
        </div>
        <h2 className="mt-4 text-xl font-semibold tracking-tight text-white">Sign in to Woobe</h2>
        <p className="mt-1.5 text-sm leading-5 text-muted">Access your workspace and operate AI products in production.</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-300">Email</label>
          <Input
            type="email"
            autoComplete="email"
            {...register('email')}
            error={errors.email?.message}
            placeholder="you@company.com"
            className="bg-background/60 text-white"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-300">Password</label>
          <Input
            type="password"
            autoComplete="current-password"
            {...register('password')}
            error={errors.password?.message}
            placeholder="Enter your password"
            className="bg-background/60 text-white"
          />
        </div>

        {errors.root && (
          <div className="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/[0.06] p-3 text-xs leading-5 text-red-200">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-300" />
            <p>{errors.root.message}</p>
          </div>
        )}

        <Button type="submit" loading={isSubmitting} className="h-10 w-full">
          Sign in
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </form>

      <div className="mt-5 rounded-xl border border-border/80 bg-background/45 px-4 py-3 text-center text-xs text-muted">
        Don&apos;t have an account?{' '}
        <Link to="/register" className="font-medium text-primary-light transition-colors hover:text-white">Create workspace</Link>
      </div>
    </div>
  )
}
