import { useState, type ChangeEvent } from 'react'
import type { UseFormReturn } from 'react-hook-form'
import { Input } from '@/components/ui/Input'
import { slugify } from '@/lib/slug'
import { AutoSlugHelp } from './AutoSlugHelp'

interface NameSlugFieldsProps {
  form: UseFormReturn<any>
  namePath: string
  slugPath: string
  namePlaceholder: string
  slugPlaceholder?: string
  fallback: string
  uniqueScope: string
  lockSlug?: boolean
}

export function NameSlugFields({
  form,
  namePath,
  slugPath,
  namePlaceholder,
  slugPlaceholder = 'slug',
  fallback,
  uniqueScope,
  lockSlug = false,
}: NameSlugFieldsProps) {
  const [isSlugDirty, setIsSlugDirty] = useState(false)
  const nameField = form.register(namePath)
  const slugField = form.register(slugPath)
  const errors = form.formState.errors as Record<string, { message?: string } | undefined>

  const handleNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    nameField.onChange(event)
    if (lockSlug || !isSlugDirty) {
      form.setValue(slugPath, slugify(event.target.value, fallback), {
        shouldDirty: true,
        shouldValidate: true,
      })
    }
  }

  const handleSlugChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (lockSlug) return
    setIsSlugDirty(true)
    slugField.onChange(event)
  }

  return (
    <>
      <Input
        {...nameField}
        onChange={handleNameChange}
        error={errors[namePath]?.message}
        placeholder={namePlaceholder}
      />
      <div>
        <Input
          {...slugField}
          readOnly={lockSlug}
          aria-readonly={lockSlug}
          onChange={handleSlugChange}
          error={errors[slugPath]?.message}
          placeholder={slugPlaceholder}
          className={lockSlug ? 'cursor-default bg-background/50 text-muted' : undefined}
        />
        <AutoSlugHelp scope={uniqueScope} />
      </div>
    </>
  )
}
