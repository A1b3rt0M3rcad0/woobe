export const woobeColors = {
  background: 'rgb(var(--woobe-canvas, 248 247 245) / <alpha-value>)',
  foreground: 'rgb(var(--woobe-ink, 36 35 33) / <alpha-value>)',
  'primary-foreground': '#fffefd',
  surface: 'rgb(var(--woobe-surface, 255 254 253) / <alpha-value>)',
  control: 'rgb(var(--woobe-control, 239 238 235) / <alpha-value>)',
  border: 'rgb(var(--woobe-border, 227 225 221) / <alpha-value>)',
  'control-border': 'rgb(var(--woobe-control-border, 140 134 125) / <alpha-value>)',
  'brand-mark': '#ff5500',
  primary: {
    DEFAULT: '#242321',
    hover: '#36332f',
    light: 'rgb(var(--woobe-link, 173 57 0) / <alpha-value>)',
  },
  muted: {
    DEFAULT: 'rgb(var(--woobe-muted, 107 104 99) / <alpha-value>)',
    foreground: 'rgb(var(--woobe-muted, 107 104 99) / <alpha-value>)',
  },
  accent: {
    DEFAULT: 'rgb(var(--woobe-border, 227 225 221) / <alpha-value>)',
    foreground: 'rgb(var(--woobe-ink, 36 35 33) / <alpha-value>)',
  },
  success: '#197542',
  warning: '#9b5700',
  error: '#b42318',
  destructive: '#b42318', // Existing feature error copy uses this semantic alias.
  network: '#7041cc',
} as const

/**
 * Presentation tokens for syntax/code surfaces that cannot consume Tailwind
 * classes directly (CodeMirror, canvas renderers, third-party editors, etc.).
 */
export const woobeCodeTheme = {
  background: 'var(--woobe-editor-background, #f8f7f5)',
  foreground: 'var(--woobe-editor-foreground, #242321)',
  caret: woobeColors.primary.DEFAULT,
  gutterBackground: 'var(--woobe-editor-background, #f8f7f5)',
  gutterForeground: '#6b6863',
  border: 'var(--woobe-editor-border, #e3e1dd)',
  activeLine: 'var(--woobe-editor-active, #efeeeb)',
  selection: 'rgb(255 85 0 / 0.12)',
  matchingBracketBackground: '#ffe4d6',
  matchingBracketBorder: '#6b6863',
  tooltipBackground: 'var(--woobe-editor-surface, #fffefd)',
  tooltipForeground: 'var(--woobe-editor-foreground, #242321)',
  scrollbar: 'rgb(148 163 184 / 0.15)',
  scrollbarHover: 'rgb(148 163 184 / 0.35)',
  syntax: {
    property: '#242321',
    string: '#9b5700',
    number: '#9b5700',
    boolean: '#197542',
    null: '#9b5700',
    punctuation: '#6b6863',
  },
} as const

export type WoobeColors = typeof woobeColors
export type WoobeCodeTheme = typeof woobeCodeTheme
