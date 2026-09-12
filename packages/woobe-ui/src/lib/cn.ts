type ClassNameValue = string | false | null | undefined

export function cn(...values: ClassNameValue[]) {
  return values.filter(Boolean).join(' ')
}
