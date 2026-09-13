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
      <header className="mb-[18px]">
        <h1 className="font-mono text-[16px] font-bold leading-[20px] tracking-[0.01em] text-slate-50">
          Create workspace
        </h1>
        <p className="mt-[4px] font-mono text-[9px] leading-[14px] text-muted-foreground">
          Create the account that will own your Woobe workspace.
        </p>
      </header>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-[14px]" noValidate>
        <Field className="gap-[6px]">
          <FieldLabel
            htmlFor="register-email"
            className="font-mono text-[9px] font-bold uppercase leading-[12px] tracking-[0.1em] text-muted-foreground"
          >
            Email
          </FieldLabel>
          <Input
            id="register-email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? 'register-email-error' : undefined}
            className="h-[34px] rounded-[3px] bg-control px-[10px] font-mono text-[10px] leading-[14px] text-slate-100"
            {...register('email')}
          />
          {errors.email?.message && (
            <FieldError id="register-email-error" className="font-mono text-[9px] leading-[13px]">
              {errors.email.message}
            </FieldError>
          )}
        </Field>

        <Field className="gap-[6px]">
          <FieldLabel
            htmlFor="register-password"
            className="font-mono text-[9px] font-bold uppercase leading-[12px] tracking-[0.1em] text-muted-foreground"
          >
            Password
          </FieldLabel>
          <Input
            id="register-password"
            type="password"
            autoComplete="new-password"
            placeholder="At least 6 characters"
            invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? 'register-password-error' : undefined}
            className="h-[34px] rounded-[3px] bg-control px-[10px] font-mono text-[10px] leading-[14px] text-slate-100"
            {...register('password')}
          />
          {errors.password?.message && (
            <FieldError id="register-password-error" className="font-mono text-[9px] leading-[13px]">
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
          Create workspace
        </Button>
      </form>

      <div className="mt-[18px] border-t border-border pt-[13px] text-center font-mono text-[9px] leading-[13px] text-muted-foreground">
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
