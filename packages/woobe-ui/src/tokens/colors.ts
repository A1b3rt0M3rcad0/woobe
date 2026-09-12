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

/**
 * Presentation tokens for syntax/code surfaces that cannot consume Tailwind
 * classes directly (CodeMirror, canvas renderers, third-party editors, etc.).
 */
export const woobeCodeTheme = {
  background: woobeColors.control,
  foreground: '#cbd5e1',
  caret: woobeColors.primary.DEFAULT,
  gutterBackground: woobeColors.control,
  gutterForeground: woobeColors.muted.DEFAULT,
  border: woobeColors.border,
  activeLine: woobeColors.accent.DEFAULT,
  selection: 'rgb(59 130 246 / 0.18)',
  matchingBracketBackground: 'rgb(30 41 59 / 0.82)',
  matchingBracketBorder: woobeColors.muted.DEFAULT,
  tooltipBackground: woobeColors.surface,
  tooltipForeground: woobeColors.accent.foreground,
  scrollbar: 'rgb(148 163 184 / 0.15)',
  scrollbarHover: 'rgb(148 163 184 / 0.35)',
  syntax: {
    property: woobeColors.primary.light,
    string: woobeColors.warning,
    number: '#fdba74',
    boolean: woobeColors.success,
    null: '#fdba74',
    punctuation: woobeColors.muted.foreground,
  },
} as const

export type WoobeColors = typeof woobeColors
export type WoobeCodeTheme = typeof woobeCodeTheme
