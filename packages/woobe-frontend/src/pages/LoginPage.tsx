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
      <header className="mb-ui-content-gutter">
        <h1 className="font-mono text-page-title font-bold text-slate-50">
          Sign in to Woobe
        </h1>
        <p className="mt-ui-xs font-mono text-product-caption text-muted-foreground">
          Access your workspace and production operations.
        </p>
      </header>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-ui-stack" noValidate>
        <Field className="gap-ui-control-gap">
          <FieldLabel htmlFor="login-email" className="font-bold tracking-ui-eyebrow">
            Email
          </FieldLabel>
          <Input
            id="login-email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? 'login-email-error' : undefined}
            className="h-control rounded-control bg-control px-ui-md font-mono text-system-control text-slate-100"
            {...register('email')}
          />
          {errors.email?.message && (
            <FieldError id="login-email-error" className="font-mono text-product-caption">
              {errors.email.message}
            </FieldError>
          )}
        </Field>

        <Field className="gap-ui-control-gap">
          <FieldLabel htmlFor="login-password" className="font-bold tracking-ui-eyebrow">
            Password
          </FieldLabel>
          <Input
            id="login-password"
            type="password"
            autoComplete="current-password"
            placeholder="Enter your password"
            invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? 'login-password-error' : undefined}
            className="h-control rounded-control bg-control px-ui-md font-mono text-system-control text-slate-100"
            {...register('password')}
          />
          {errors.password?.message && (
            <FieldError id="login-password-error" className="font-mono text-product-caption">
              {errors.password.message}
            </FieldError>
          )}
        </Field>

        {errors.root && (
          <Alert variant="destructive" className="flex items-start gap-ui-sm rounded-control px-ui-md py-ui-sm font-mono text-product-caption">
            <AlertTriangle className="mt-px h-icon-sm w-icon-sm shrink-0 text-red-300" />
            <p>{errors.root.message}</p>
          </Alert>
        )}

        <Button type="submit" loading={isSubmitting} className="w-full font-normal">
          Sign in
        </Button>
      </form>

      <div className="mt-ui-content-gutter border-t border-border pt-ui-md text-center font-mono text-system-meta text-muted-foreground">
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
