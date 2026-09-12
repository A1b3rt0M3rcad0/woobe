export const woobeColors = {
  background: '#020817',
  surface: '#0f1729',
  control: '#0b1220',
  border: '#1e293b',
  primary: {
    DEFAULT: '#3b82f6',
    hover: '#2563eb',
    light: '#93c5fd',
  },
  muted: {
    DEFAULT: '#64748b',
    foreground: '#94a3b8',
  },
  accent: {
    DEFAULT: '#1e293b',
    foreground: '#f8fafc',
  },
  success: '#34d399',
  warning: '#f59e0b',
  error: '#ef4444',
  network: '#8b5cf6',
} as const

export type WoobeColors = typeof woobeColors
