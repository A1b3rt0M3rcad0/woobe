import { useState, type ChangeEvent } from 'react'
import type { UseFormReturn, FieldValues, Path } from 'react-hook-form'
import { Input } from '@/components/ui/Input'
import { slugify } from '@/lib/slug'
import { AutoSlugHelp } from './AutoSlugHelp'

interface NameSlugFieldsProps<T extends FieldValues> {
  form: UseFormReturn<T>
  namePath: Path<T>
  slugPath: Path<T>
  namePlaceholder: string
  slugPlaceholder?: string
  fallback: string
  uniqueScope: string
}

export function NameSlugFields<T extends FieldValues>({
  form,
  namePath,
  slugPath,
  namePlaceholder,
  slugPlaceholder = 'slug',
  fallback,
  uniqueScope,
}: NameSlugFieldsProps<T>) {
  const [isSlugDirty, setIsSlugDirty] = useState(false)
  const nameField = form.register(namePath)
  const slugField = form.register(slugPath)

  const handleNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    nameField.onChange(event)
    if (!isSlugDirty) {
      form.setValue(slugPath, slugify(event.target.value, fallback) as never, {
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
        error={form.formState.errors[namePath]?.message as string | undefined}
        placeholder={namePlaceholder}
      />
      <div>
        <Input
          {...slugField}
          onChange={handleSlugChange}
          error={form.formState.errors[slugPath]?.message as string | undefined}
          placeholder={slugPlaceholder}
        />
        <AutoSlugHelp scope={uniqueScope} />
      </div>
    </>
  )
}
