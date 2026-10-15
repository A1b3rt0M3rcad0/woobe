export { woobeFontSizes } from './typography'
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
  sans: ['var(--g-font-sans)'],
  serif: ['var(--g-font-serif)'],
  mono: ['var(--g-font-mono)'],
} as const

export const woobeRadius = {
  technical: '0.25rem',
  control: '0.375rem',
  container: '0.625rem',
} as const
