export type RuntimeEnvironmentAppearanceKey = 'draft' | 'staging' | 'production'

export interface RuntimeEnvironmentAppearance {
  label: string
  dot: string
  border: string
  background: string
  subtleBackground: string
  text: string
  tone: string
  card: string
  chartColor: string
}

export const ENVIRONMENT_APPEARANCE: Record<RuntimeEnvironmentAppearanceKey, RuntimeEnvironmentAppearance> = {
  draft: {
    label: 'Draft',
    dot: 'bg-blue-400',
    border: 'border-blue-500/35',
    background: 'bg-blue-500/10',
    subtleBackground: 'bg-blue-500/[0.04]',
    text: 'text-blue-300',
    tone: 'border-blue-500/35 bg-blue-500/10 text-blue-300',
    card: 'border-blue-500/35 bg-blue-500/[0.04]',
    chartColor: '#3b82f6',
  },
  staging: {
    label: 'Staging',
    dot: 'bg-amber-400',
    border: 'border-amber-500/35',
    background: 'bg-amber-500/10',
    subtleBackground: 'bg-amber-500/[0.04]',
    text: 'text-amber-300',
    tone: 'border-amber-500/35 bg-amber-500/10 text-amber-300',
    card: 'border-amber-500/35 bg-amber-500/[0.04]',
    chartColor: '#fbbf24',
  },
  production: {
    label: 'Production',
    dot: 'bg-emerald-400',
    border: 'border-emerald-500/35',
    background: 'bg-emerald-500/10',
    subtleBackground: 'bg-emerald-500/[0.03]',
    text: 'text-emerald-300',
    tone: 'border-emerald-500/35 bg-emerald-500/10 text-emerald-300',
    card: 'border-emerald-500/35 bg-emerald-500/[0.03]',
    chartColor: '#22c55e',
  },
}

export function isRuntimeEnvironmentAppearanceKey(value: string): value is RuntimeEnvironmentAppearanceKey {
  return value === 'draft' || value === 'staging' || value === 'production'
}

export function getEnvironmentAppearance(value: string): RuntimeEnvironmentAppearance | null {
  const normalized = value.trim().toLowerCase()
  return isRuntimeEnvironmentAppearanceKey(normalized) ? ENVIRONMENT_APPEARANCE[normalized] : null
}
