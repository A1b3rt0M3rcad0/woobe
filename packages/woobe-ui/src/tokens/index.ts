export { woobeCodeTheme, woobeColors, type WoobeCodeTheme, type WoobeColors } from './colors'
export {
  woobeBreakpoints,
  woobeControl,
  woobeDensity,
  woobeLayers,
  woobeLayout,
  woobePattern,
  woobeShadow,
  woobeSpacing,
  woobeTypographyScale,
  woobeTypographyTracking,
} from './foundations'

export const woobeTypography = {
  sans: ['Inter', 'system-ui', 'sans-serif'],
  mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
} as const

export const woobeRadius = {
  technical: '0.125rem',
  control: '0.1875rem',
  container: '0.25rem',
} as const
