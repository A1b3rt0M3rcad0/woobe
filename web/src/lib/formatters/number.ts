export function formatNumber(
  value: number | null | undefined,
  digits = 2,
  fallback = "—"
): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return fallback;
  }

  return value.toFixed(digits);
}

export function formatCurrency(
  value: number | null | undefined,
  digits = 4,
  fallback = "—"
): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return fallback;
  }

  return `$${value.toFixed(digits)}`;
}

export function formatLatency(
  value: number | null | undefined,
  fallback = "—"
): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return fallback;
  }

  return `${value.toFixed(0)}ms`;
}
