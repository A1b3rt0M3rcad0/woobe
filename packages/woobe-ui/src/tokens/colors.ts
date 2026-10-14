export const woobeColors = {
  background: 'rgb(var(--woobe-canvas, 247 247 244) / <alpha-value>)',
  foreground: 'rgb(var(--woobe-ink, 25 35 31) / <alpha-value>)',
  'primary-foreground': '#ffffff',
  surface: 'rgb(var(--woobe-surface, 255 255 255) / <alpha-value>)',
  control: 'rgb(var(--woobe-control, 242 243 240) / <alpha-value>)',
  border: 'rgb(var(--woobe-border, 217 222 218) / <alpha-value>)',
  primary: {
    DEFAULT: '#2459d3',
    hover: '#1947b4',
    light: 'rgb(var(--woobe-link, 36 89 211) / <alpha-value>)',
  },
  muted: {
    DEFAULT: 'rgb(var(--woobe-muted, 98 109 104) / <alpha-value>)',
    foreground: 'rgb(var(--woobe-muted, 98 109 104) / <alpha-value>)',
  },
  accent: {
    DEFAULT: 'rgb(var(--woobe-border, 217 222 218) / <alpha-value>)',
    foreground: 'rgb(var(--woobe-ink, 25 35 31) / <alpha-value>)',
  },
  success: '#18734a',
  warning: '#946000',
  error: '#b92f3c',
  network: '#8b5cf6',
} as const

/**
 * Presentation tokens for syntax/code surfaces that cannot consume Tailwind
 * classes directly (CodeMirror, canvas renderers, third-party editors, etc.).
 */
export const woobeCodeTheme = {
  background: 'var(--woobe-editor-background, #f2f3f0)',
  foreground: 'var(--woobe-editor-foreground, #19231f)',
  caret: woobeColors.primary.DEFAULT,
  gutterBackground: 'var(--woobe-editor-background, #f2f3f0)',
  gutterForeground: '#626d68',
  border: 'var(--woobe-editor-border, #d9deda)',
  activeLine: 'var(--woobe-editor-active, #e7ece8)',
  selection: 'rgb(59 130 246 / 0.18)',
  matchingBracketBackground: '#dce5df',
  matchingBracketBorder: '#626d68',
  tooltipBackground: 'var(--woobe-editor-surface, #ffffff)',
  tooltipForeground: 'var(--woobe-editor-foreground, #19231f)',
  scrollbar: 'rgb(148 163 184 / 0.15)',
  scrollbarHover: 'rgb(148 163 184 / 0.35)',
  syntax: {
    property: '#2459d3',
    string: '#946000',
    number: '#946000',
    boolean: '#18734a',
    null: '#946000',
    punctuation: '#626d68',
  },
} as const

export type WoobeColors = typeof woobeColors
export type WoobeCodeTheme = typeof woobeCodeTheme
