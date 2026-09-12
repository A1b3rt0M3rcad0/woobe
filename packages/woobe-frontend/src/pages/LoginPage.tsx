import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowRight, LockKeyhole } from 'lucide-react'
import { Alert, Badge, Button, Field, FieldError, FieldLabel, Input } from '@woobe/ui'
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
      <div className="mb-6">
        <Badge variant="outline" className="font-mono uppercase tracking-[0.1em]">
          <LockKeyhole className="h-3 w-3 text-primary-light" />
          Control plane access
        </Badge>
        <h2 className="mt-5 text-[22px] font-semibold tracking-[-0.02em] text-slate-50">Sign in to Woobe</h2>
        <p className="mt-1.5 text-sm leading-5 text-muted-foreground">
          Authenticate to access your workspace and production operations.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Field>
          <FieldLabel htmlFor="login-email">Email</FieldLabel>
          <Input
            id="login-email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? 'login-email-error' : undefined}
            {...register('email')}
          />
          {errors.email?.message && (
            <FieldError id="login-email-error">{errors.email.message}</FieldError>
          )}
        </Field>

        <Field>
          <FieldLabel htmlFor="login-password">Password</FieldLabel>
          <Input
            id="login-password"
            type="password"
            autoComplete="current-password"
            placeholder="Enter your password"
            invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? 'login-password-error' : undefined}
            {...register('password')}
          />
          {errors.password?.message && (
            <FieldError id="login-password-error">{errors.password.message}</FieldError>
          )}
        </Field>

        {errors.root && (
          <Alert variant="destructive" className="flex items-start gap-2.5">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-300" />
            <p>{errors.root.message}</p>
          </Alert>
        )}

        <Button type="submit" loading={isSubmitting} className="mt-1 h-10 w-full">
          Sign in
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </form>

      <div className="mt-6 border-t border-border pt-4 text-center text-xs text-muted-foreground">
        Don&apos;t have an account?{' '}
        <Link
          to="/register"
          className="font-medium text-primary-light transition-colors hover:text-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
        >
          Create workspace
        </Link>
      </div>
    </div>
  )
}
