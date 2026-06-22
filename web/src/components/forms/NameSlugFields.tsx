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
}

export function NameSlugFields({
  form,
  namePath,
  slugPath,
  namePlaceholder,
  slugPlaceholder = 'slug',
  fallback,
  uniqueScope,
}: NameSlugFieldsProps) {
  const [isSlugDirty, setIsSlugDirty] = useState(false)
  const nameField = form.register(namePath)
  const slugField = form.register(slugPath)
  const errors = form.formState.errors as Record<string, { message?: string } | undefined>

  const handleNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    nameField.onChange(event)
    if (!isSlugDirty) {
      form.setValue(slugPath, slugify(event.target.value, fallback), {
        shouldDirty: true,
        shouldValidate: true,
      })
    }
  }

  const handleSlugChange = (event: ChangeEvent<HTMLInputElement>) => {
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
          onChange={handleSlugChange}
          error={errors[slugPath]?.message}
          placeholder={slugPlaceholder}
        />
        <AutoSlugHelp scope={uniqueScope} />
      </div>
    </>
  )
}
