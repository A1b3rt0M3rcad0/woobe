export const woobeTypographyScale = {
  chromeNano: ['0.5rem', { lineHeight: '0.625rem', letterSpacing: '0' }],
  chromeMeta: ['0.5rem', { lineHeight: '0.625rem', letterSpacing: '0' }],
  chromeLabel: ['0.5625rem', { lineHeight: '0.75rem', letterSpacing: '0' }],
  chromeControl: ['0.625rem', { lineHeight: '0.875rem', letterSpacing: '0' }],
  systemNano: ['0.5rem', { lineHeight: '0.625rem', letterSpacing: '0' }],
  systemMicro: ['0.5rem', { lineHeight: '0.6875rem', letterSpacing: '0' }],
  systemMeta: ['0.5625rem', { lineHeight: '0.75rem', letterSpacing: '0' }],
  systemLabel: ['0.5625rem', { lineHeight: '0.75rem', letterSpacing: '0.01em' }],
  systemControl: ['0.625rem', { lineHeight: '0.875rem', letterSpacing: '0' }],
  systemValue: ['0.6875rem', { lineHeight: '0.875rem', letterSpacing: '0' }],
  systemHeading: ['0.75rem', { lineHeight: '1rem', letterSpacing: '0.015em' }],
  productCaption: ['0.5625rem', { lineHeight: '0.875rem', letterSpacing: '0' }],
  productSmall: ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0' }],
  productLabel: ['0.75rem', { lineHeight: '1rem', letterSpacing: '0' }],
  productBody: ['0.8125rem', { lineHeight: '1.25rem', letterSpacing: '0' }],
  productReading: ['0.875rem', { lineHeight: '1.375rem', letterSpacing: '0' }],
  entityTitle: ['0.8125rem', { lineHeight: '1.125rem', letterSpacing: '0' }],
  sectionTitle: ['0.75rem', { lineHeight: '1rem', letterSpacing: '0.015em' }],
  brandTitle: ['0.875rem', { lineHeight: '1.0625rem', letterSpacing: '0.02em' }],
  brandCaption: ['0.625rem', { lineHeight: '0.75rem', letterSpacing: '0.12em' }],
  pageTitle: ['1rem', { lineHeight: '1.25rem', letterSpacing: '0.01em' }],
  codeCompact: ['0.625rem', { lineHeight: '0.9375rem', letterSpacing: '0' }],
  codeDefault: ['0.6875rem', { lineHeight: '1.0625rem', letterSpacing: '0' }],
  headingSmall: ['0.875rem', { lineHeight: '1.25rem', letterSpacing: '-0.01em' }],
  heading: ['1rem', { lineHeight: '1.375rem', letterSpacing: '0.01em' }],
  headingLarge: ['1.125rem', { lineHeight: '1.625rem', letterSpacing: '-0.02em' }],
  metric: ['1.25rem', { lineHeight: '1.5rem', letterSpacing: '-0.02em' }],
  metricEmphasis: ['0.9375rem', { lineHeight: '0.9375rem', letterSpacing: '-0.01em' }],
  metricCompact: ['1.0625rem', { lineHeight: '1.0625rem', letterSpacing: '-0.02em' }],
  metricLarge: ['1.75rem', { lineHeight: '1.75rem', letterSpacing: '-0.04em' }],
} as const

export const woobeTypographyTracking = {
  label: '0.08em',
  eyebrow: '0.12em',
} as const

export const woobeSpacing = {
  hairline: '0.125rem',
  controlInset: '0.1875rem',
  controlGap: '0.375rem',
  xs: '0.25rem',
  sm: '0.5rem',
  md: '0.75rem',
  stack: '0.875rem',
  panelInset: '0.9375rem',
  lg: '1rem',
  contentGutter: '1.125rem',
  xl: '1.25rem',
  xxl: '1.5rem',
} as const

export const woobeControl = {
  height: {
    technical: '1.5rem',
    segment: '1.625rem',
    compact: '1.875rem',
    default: '2.125rem',
    navigation: '2.25rem',
    large: '2.375rem',
    row: '2.625rem',
    header: '3rem',
    dialogHeader: '3.25rem',
    workspaceHeader: '3.375rem',
  },
  minHeight: {
    textareaCompact: '4.875rem',
    textarea: '5.75rem',
  },
  maxHeight: {
    multiline: '10rem',
  },
  icon: {
    small: '0.75rem',
    default: '0.875rem',
    large: '1rem',
    brand: '1.25rem',
  },
} as const

export const woobeBreakpoints = {
  sm: '40rem',
  md: '48rem',
  lg: '64rem',
  xl: '80rem',
  '2xl': '96rem',
  '2k': '128rem',
} as const

export const woobeLayout = {
  projectSidebar: '16.125rem',
  projectSidebarHeader: '4.5rem',
  sidebarContextMenuMaxHeight: '26.25rem',
  popoverCompactMinWidth: '12.5rem',
  popoverMaxHeight: '17.5rem',
  playgroundRail: '3.75rem',
  playgroundInspectorTop: '8rem',
  playgroundAgentNameMax: '13.75rem',
  playgroundAgentMetaMax: '18.75rem',
  playgroundTraceListMaxHeight: '14.875rem',
  operationsPanel: '23.25rem',
  inspector: '23.75rem',
  inspectorExpanded: '38.75rem',
  conversationRailCompact: '1.5rem',
  conversationRail: '3rem',
  conversationIndentCompact: '2rem',
  conversationIndent: '3.625rem',
  conversationContentMax: '80%',
  conversationContentCompactMax: '88%',
  resourceCardMinHeight: '8rem',
  contentTableCellMin: '9rem',
  resourceMax: '93.75rem',
  resourceWideMax: '100rem',
  narrowFormMax: '25.25rem',
  dialogCompact: '32.5rem',
  dialogDefault: '45rem',
  dialogWide: '68.75rem',
  dialogSidebar: '15.625rem',
  dialogContentMax: '47.5rem',
  dialogMaxHeight: 'calc(100svh - 2rem)',
  dialogWorkspaceHeight: 'min(40rem, calc(100svh - 7rem))',
  focusWorkspaceWidth: 'min(94vw, 93.75rem)',
  focusWorkspaceHeight: 'min(88svh, 57.5rem)',
  codeSnippetCompact: '5.25rem',
  codeSnippetDefault: '7.5rem',
  codeInlineCompact: '8.75rem',
  codeInlineDefault: '10rem',
  codeStructuredCompact: '13.75rem',
  codeStructuredDefault: '21.25rem',
  codeEditorCompact: '11.25rem',
  codeEditorMax: '22.5rem',
} as const

export const woobePattern = {
  technicalGridImage: 'linear-gradient(rgb(148 163 184 / 0.02) 1px, transparent 1px), linear-gradient(90deg, rgb(148 163 184 / 0.02) 1px, transparent 1px)',
  technicalGridSize: '2rem 2rem',
} as const

export const woobeShadow = {
  none: 'none',
  popup: '0 12px 32px rgb(0 0 0 / 0.28)',
  overlay: '0 18px 48px rgb(0 0 0 / 0.30)',
} as const

export const woobeLayers = {
  base: 0,
  sticky: 20,
  workspace: 40,
  popover: 100,
  playgroundChrome: 200,
  modal: 300,
  nestedModal: 400,
  focus: 500,
  toast: 1100,
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
