import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from 'react-router-dom'
import { AlertTriangle, ArrowRight, Building2, ShieldCheck } from 'lucide-react'
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
      <div className="mb-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-background/60 px-2.5 py-1 text-[11px] font-medium text-muted">
          <Building2 className="h-3 w-3 text-primary-light" />
          Organization workspace
        </div>
        <h2 className="mt-4 text-xl font-semibold tracking-tight text-white">Create your workspace</h2>
        <p className="mt-1.5 text-sm leading-5 text-muted">Start with one organization and deploy agents from a controlled project surface.</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-300">Organization</label>
          <Input
            {...register('organization_name')}
            error={errors.organization_name?.message}
            placeholder="Your company or workspace name"
            className="bg-background/60 text-white"
          />
          <p className="mt-1.5 text-[11px] leading-4 text-muted">This becomes the owner workspace for projects, releases and billing.</p>
        </div>

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
          <p>Your first organization becomes the control boundary for projects, agents, tools and runtime access.</p>
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
