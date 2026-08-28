import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowRight } from 'lucide-react'
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
      <header className="mb-6">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.16em] text-muted">
          Control plane access
        </p>
        <h2 className="mt-3 text-xl font-semibold leading-6 tracking-tight text-white">Sign in</h2>
        <p className="mt-1.5 text-[13px] leading-5 text-muted">Access the Woobe control plane.</p>
      </header>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label htmlFor="login-email" className="mb-2 block text-xs font-medium text-slate-300">
            Email
          </label>
          <Input
            id="login-email"
            type="email"
            autoComplete="email"
            aria-invalid={Boolean(errors.email)}
            {...register('email')}
            error={errors.email?.message}
            placeholder="you@company.com"
            className="h-10 bg-background/70 text-white shadow-none"
          />
        </div>

        <div>
          <label htmlFor="login-password" className="mb-2 block text-xs font-medium text-slate-300">
            Password
          </label>
          <Input
            id="login-password"
            type="password"
            autoComplete="current-password"
            aria-invalid={Boolean(errors.password)}
            {...register('password')}
            error={errors.password?.message}
            placeholder="Enter your password"
            className="h-10 bg-background/70 text-white shadow-none"
          />
        </div>

        {errors.root && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/[0.04] p-3 text-xs leading-5 text-red-200"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-300" />
            <p>{errors.root.message}</p>
          </div>
        )}

        <Button type="submit" loading={isSubmitting} className="h-10 w-full shadow-none">
          Sign in
          <ArrowRight className="ml-2 h-3.5 w-3.5" />
        </Button>
      </form>

      <div className="mt-6 border-t border-border/80 pt-4 text-center text-xs text-muted">
        New to Woobe?{' '}
        <Link to="/register" className="font-medium text-primary-light transition-colors hover:text-white">
          Create an account
        </Link>
      </div>
    </div>
  )
}
