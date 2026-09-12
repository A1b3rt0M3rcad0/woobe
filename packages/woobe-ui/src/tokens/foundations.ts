export const woobeTypographyScale = {
  systemMeta: ['0.5rem', { lineHeight: '0.875rem', letterSpacing: '0.02em' }],
  systemLabel: ['0.5625rem', { lineHeight: '0.875rem', letterSpacing: '0.01em' }],
  systemControl: ['0.625rem', { lineHeight: '1rem', letterSpacing: '0' }],
  systemHeading: ['0.75rem', { lineHeight: '1rem', letterSpacing: '0.01em' }],
  productCaption: ['0.5625rem', { lineHeight: '1rem', letterSpacing: '0' }],
  productSmall: ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0' }],
  productBody: ['0.8125rem', { lineHeight: '1.25rem', letterSpacing: '0' }],
  headingSmall: ['0.875rem', { lineHeight: '1.25rem', letterSpacing: '-0.01em' }],
  heading: ['1rem', { lineHeight: '1.5rem', letterSpacing: '-0.015em' }],
  headingLarge: ['1.125rem', { lineHeight: '1.625rem', letterSpacing: '-0.02em' }],
  metric: ['1.25rem', { lineHeight: '1.5rem', letterSpacing: '-0.02em' }],
} as const

export const woobeSpacing = {
  hairline: '0.125rem',
  xs: '0.25rem',
  sm: '0.5rem',
  md: '0.75rem',
  lg: '1rem',
  xl: '1.25rem',
  xxl: '1.5rem',
} as const

export const woobeControl = {
  height: {
    segment: '1.6875rem',
    compact: '1.875rem',
    default: '2.125rem',
    large: '2.375rem',
    row: '2.625rem',
    header: '3rem',
    dialogHeader: '3.25rem',
    workspaceHeader: '3.375rem',
  },
  minHeight: {
    textarea: '5.75rem',
  },
  icon: {
    small: '0.75rem',
    default: '0.875rem',
    large: '1rem',
  },
} as const

export const woobeBreakpoints = {
  sm: '40rem',
  md: '48rem',
  lg: '64rem',
  xl: '80rem',
  '2xl': '96rem',
} as const

export const woobeLayout = {
  projectSidebar: '16.125rem',
  playgroundRail: '3.25rem',
  playgroundInspectorTop: '8rem',
  operationsPanel: '23.25rem',
  inspector: '23.75rem',
  inspectorExpanded: '38.75rem',
  resourceMax: '93.75rem',
  resourceWideMax: '100rem',
  dialogCompact: '32.5rem',
  dialogDefault: '45rem',
  dialogWide: '68.75rem',
} as const

export const woobeShadow = {
  none: 'none',
  popup: '0 12px 32px rgb(0 0 0 / 0.28)',
  overlay: '0 18px 48px rgb(0 0 0 / 0.30)',
} as const

export const woobeLayers = {
  base: '0',
  sticky: '20',
  workspace: '40',
  popover: '200',
  overlay: '900',
  modal: '1000',
  toast: '1100',
} as const

export const woobeDensity = {
  compact: {
    gap: woobeSpacing.sm,
    padding: woobeSpacing.sm,
    controlHeight: woobeControl.height.compact,
  },
  default: {
    gap: woobeSpacing.md,
    padding: woobeSpacing.md,
    controlHeight: woobeControl.height.default,
  },
  comfortable: {
    gap: woobeSpacing.lg,
    padding: woobeSpacing.lg,
    controlHeight: woobeControl.height.large,
  },
} as const
