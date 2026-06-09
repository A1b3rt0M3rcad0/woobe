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

export function formatTokens(
  value: number | null | undefined,
  fallback = "—"
): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return fallback;
  }
  return value.toLocaleString();
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

  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)}s`;
  }
  return `${value.toFixed(0)}ms`;
}

export function formatDateTime(
  value: string | null | undefined,
  fallback = "—"
): string {
  if (!value) return fallback;
  try {
    const d = new Date(value);
    return d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return fallback;
  }
}

export function formatTraceStatus(
  value: string | null | undefined,
  fallback = "—"
): string {
  if (!value) return fallback;
  return value.charAt(0).toUpperCase() + value.slice(1);
}
