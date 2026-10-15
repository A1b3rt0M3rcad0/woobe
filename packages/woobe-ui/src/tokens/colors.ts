export const woobeColors = {
  background: 'rgb(var(--woobe-canvas, 243 241 237) / <alpha-value>)',
  foreground: 'rgb(var(--woobe-ink, 36 35 33) / <alpha-value>)',
  'primary-foreground': 'rgb(var(--woobe-on-primary, 255 253 249) / <alpha-value>)',
  workspace: 'rgb(var(--woobe-workspace, 245 243 239) / <alpha-value>)',
  elevated: 'rgb(var(--woobe-elevated, 255 254 252) / <alpha-value>)',
  selected: 'rgb(var(--woobe-selected, 241 223 208) / <alpha-value>)',
  surface: 'rgb(var(--woobe-surface, 255 254 253) / <alpha-value>)',
  'panel-band': 'rgb(var(--woobe-panel-band, 246 244 240) / <alpha-value>)',
  control: 'rgb(var(--woobe-control, 239 238 235) / <alpha-value>)',
  border: 'rgb(var(--woobe-border, 212 208 200) / <alpha-value>)',
  'control-border': 'rgb(var(--woobe-control-border, 140 134 125) / <alpha-value>)',
  'brand-mark': '#ff5500',
  primary: {
    DEFAULT: 'rgb(var(--woobe-primary, 41 38 32) / <alpha-value>)',
    hover: 'rgb(var(--woobe-primary-hover, 64 58 50) / <alpha-value>)',
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
  success: 'rgb(var(--woobe-success, 36 104 70) / <alpha-value>)',
  warning: 'rgb(var(--woobe-warning, 134 91 19) / <alpha-value>)',
  error: 'rgb(var(--woobe-error, 178 56 52) / <alpha-value>)',
  destructive: 'rgb(var(--woobe-error, 178 56 52) / <alpha-value>)', // Existing feature error copy uses this semantic alias.
  network: 'rgb(var(--woobe-network, 109 65 168) / <alpha-value>)',
} as const

/**
 * Presentation tokens for syntax/code surfaces that cannot consume Tailwind
 * classes directly (CodeMirror, canvas renderers, third-party editors, etc.).
 */
export const woobeCodeTheme = {
  background: 'var(--woobe-editor-background, #f8f7f5)',
  foreground: 'var(--woobe-editor-foreground, #242321)',
  caret: 'rgb(var(--woobe-ink))',
  gutterBackground: 'var(--woobe-editor-background, #f8f7f5)',
  gutterForeground: 'rgb(var(--woobe-muted))',
  border: 'var(--woobe-editor-border, #e3e1dd)',
  activeLine: 'var(--woobe-editor-active, #efeeeb)',
  selection: 'rgb(var(--woobe-selected))',
  matchingBracketBackground: 'rgb(var(--woobe-selected))',
  matchingBracketBorder: 'rgb(var(--woobe-control-border))',
  tooltipBackground: 'var(--woobe-editor-surface, #fffefd)',
  tooltipForeground: 'var(--woobe-editor-foreground, #242321)',
  scrollbar: 'rgb(148 163 184 / 0.15)',
  scrollbarHover: 'rgb(148 163 184 / 0.35)',
  syntax: {
    property: 'rgb(var(--woobe-ink))',
    string: 'var(--woobe-code-string)',
    number: 'var(--woobe-code-number)',
    boolean: 'rgb(var(--woobe-success))',
    null: 'var(--woobe-code-number)',
    punctuation: 'rgb(var(--woobe-muted))',
  },
} as const

export type WoobeColors = typeof woobeColors
export type WoobeCodeTheme = typeof woobeCodeTheme
