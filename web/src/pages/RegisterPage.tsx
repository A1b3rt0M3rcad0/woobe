import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowRight, ShieldCheck } from 'lucide-react'
import { useAuth } from '@/features/auth/AuthProvider'
import { registerSchema, type RegisterFormData } from '@/features/auth/schemas'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

export default function RegisterPage() {
  const { register: registerUser } = useAuth()
  const { register, handleSubmit, formState: { errors, isSubmitting }, setError } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  })

  const onSubmit = async (data: RegisterFormData) => {
    try {
      await registerUser(data)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Registration failed'
      setError('root', { message })
    }
  }

  return (
    <div>
      <div className="mb-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-background/60 px-2.5 py-1 text-[11px] font-medium text-muted">
          <ShieldCheck className="h-3 w-3 text-primary-light" />
          Secure workspace provisioning
        </div>
        <h2 className="mt-4 text-xl font-semibold tracking-tight text-white">Create your account</h2>
        <p className="mt-1.5 text-sm leading-5 text-muted">Start building, testing and operating AI Agents from one controlled workspace.</p>
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
            autoComplete="new-password"
            {...register('password')}
            error={errors.password?.message}
            placeholder="At least 6 characters"
            className="bg-background/60 text-white"
          />
        </div>

        <div className="flex items-start gap-2 rounded-xl border border-border/80 bg-background/45 p-3 text-xs leading-5 text-muted">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary-light" />
          <p>A private Workspace is provisioned automatically. You can rename it and invite members later.</p>
        </div>

        {errors.root && (
          <div className="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/[0.06] p-3 text-xs leading-5 text-red-200">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-300" />
            <p>{errors.root.message}</p>
          </div>
        )}

        <Button type="submit" loading={isSubmitting} className="h-10 w-full">
          Create account
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </form>

      <div className="mt-5 rounded-xl border border-border/80 bg-background/45 px-4 py-3 text-center text-xs text-muted">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-primary-light transition-colors hover:text-white">Sign in</Link>
      </div>
    </div>
  )
}
