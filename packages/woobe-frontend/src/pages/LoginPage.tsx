import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import { Alert, Button, Field, FieldError, FieldLabel, Input } from '@woobe/ui'
import { useAuth } from '@/features/auth/AuthProvider'
import { loginSchema, type LoginFormData } from '@/features/auth/schemas'

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
      <header className="mb-[18px]">
        <h1 className="font-mono text-[16px] font-bold leading-[20px] tracking-[0.01em] text-slate-50">
          Sign in to Woobe
        </h1>
        <p className="mt-[4px] font-mono text-[9px] leading-[14px] text-muted-foreground">
          Access your workspace and production operations.
        </p>
      </header>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-[14px]" noValidate>
        <Field className="gap-[6px]">
          <FieldLabel
            htmlFor="login-email"
            className="font-mono text-[9px] font-bold uppercase leading-[12px] tracking-[0.1em] text-muted-foreground"
          >
            Email
          </FieldLabel>
          <Input
            id="login-email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? 'login-email-error' : undefined}
            className="h-[34px] rounded-[3px] bg-control px-[10px] font-mono text-[10px] leading-[14px] text-slate-100"
            {...register('email')}
          />
          {errors.email?.message && (
            <FieldError id="login-email-error" className="font-mono text-[9px] leading-[13px]">
              {errors.email.message}
            </FieldError>
          )}
        </Field>

        <Field className="gap-[6px]">
          <FieldLabel
            htmlFor="login-password"
            className="font-mono text-[9px] font-bold uppercase leading-[12px] tracking-[0.1em] text-muted-foreground"
          >
            Password
          </FieldLabel>
          <Input
            id="login-password"
            type="password"
            autoComplete="current-password"
            placeholder="Enter your password"
            invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? 'login-password-error' : undefined}
            className="h-[34px] rounded-[3px] bg-control px-[10px] font-mono text-[10px] leading-[14px] text-slate-100"
            {...register('password')}
          />
          {errors.password?.message && (
            <FieldError id="login-password-error" className="font-mono text-[9px] leading-[13px]">
              {errors.password.message}
            </FieldError>
          )}
        </Field>

        {errors.root && (
          <Alert variant="destructive" className="flex items-start gap-[8px] rounded-[3px] px-[10px] py-[9px] font-mono text-[9px] leading-[13px]">
            <AlertTriangle className="mt-px h-[13px] w-[13px] shrink-0 text-red-300" />
            <p>{errors.root.message}</p>
          </Alert>
        )}

        <Button type="submit" loading={isSubmitting} className="h-[34px] w-full rounded-[3px] px-[11px] font-mono text-[10px] font-normal">
          Sign in
        </Button>
      </form>

      <div className="mt-[18px] border-t border-border pt-[13px] text-center font-mono text-[9px] leading-[13px] text-muted-foreground">
        Don&apos;t have an account?{' '}
        <Link
          to="/register"
          className="text-primary-light transition-colors hover:text-slate-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        >
          Create workspace
        </Link>
      </div>
    </div>
  )
}
