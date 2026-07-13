export function formatMoney(amount: number, currency = 'USD'): string {
  const absolute = Math.abs(amount)
  if (absolute === 0) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(0)
  }
  if (absolute < 0.000001) {
    return `<${new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 6,
      maximumFractionDigits: 6,
    }).format(0.000001)}`
  }
  const maximumFractionDigits = absolute >= 1 ? 2 : absolute >= 0.01 ? 4 : 6
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: absolute >= 1 ? 2 : 4,
    maximumFractionDigits,
  }).format(amount)
}

export function formatKnownMoney(amount: number | null, currency = 'USD'): string {
  return amount === null ? 'Unknown' : formatMoney(amount, currency)
}
