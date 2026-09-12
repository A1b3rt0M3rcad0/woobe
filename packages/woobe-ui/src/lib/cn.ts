import { twMerge } from 'tailwind-merge'

type ClassNameValue = string | false | null | undefined

export function cn(...values: ClassNameValue[]) {
  return twMerge(values.filter(Boolean).join(' '))
}
