import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import { Alert, Button, Field, FieldError, FieldLabel, Input } from '@woobe/ui'
import { useAuth } from '@/features/auth/AuthProvider'
import { registerSchema, type RegisterFormData } from '@/features/auth/schemas'

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
      <header className="mb-ui-content-gutter">
        <h1 className="font-mono text-page-title font-bold text-slate-50">
          Create workspace
        </h1>
        <p className="mt-ui-xs font-mono text-product-caption text-muted-foreground">
          Create the account that will own your Woobe workspace.
        </p>
      </header>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-ui-stack" noValidate>
        <Field className="gap-ui-control-gap">
          <FieldLabel htmlFor="register-email" className="font-bold tracking-ui-eyebrow">
            Email
          </FieldLabel>
          <Input
            id="register-email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? 'register-email-error' : undefined}
            className="h-control rounded-control bg-control px-ui-md font-mono text-system-control text-slate-100"
            {...register('email')}
          />
          {errors.email?.message && (
            <FieldError id="register-email-error" className="font-mono text-product-caption">
              {errors.email.message}
            </FieldError>
          )}
        </Field>

        <Field className="gap-ui-control-gap">
          <FieldLabel htmlFor="register-password" className="font-bold tracking-ui-eyebrow">
            Password
          </FieldLabel>
          <Input
            id="register-password"
            type="password"
            autoComplete="new-password"
            placeholder="At least 6 characters"
            invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? 'register-password-error' : undefined}
            className="h-control rounded-control bg-control px-ui-md font-mono text-system-control text-slate-100"
            {...register('password')}
          />
          {errors.password?.message && (
            <FieldError id="register-password-error" className="font-mono text-product-caption">
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
          Create workspace
        </Button>
      </form>

      <div className="mt-ui-content-gutter border-t border-border pt-ui-md text-center font-mono text-system-meta text-muted-foreground">
        Already have an account?{' '}
        <Link
          to="/login"
          className="text-primary-light transition-colors hover:text-slate-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        >
          Sign in
        </Link>
      </div>
    </div>
  )
}
