export function defaultExpirationDate(days = 90): Date {
  const date = new Date()
  date.setDate(date.getDate() + days)
  date.setHours(0, 0, 0, 0)
  return date
}

// The selected local day remains usable in full, including across DST changes.
export function expirationAfterDate(date: Date | null): Date | null {
  if (!date) return null
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + 1)
}
