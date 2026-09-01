import { EditorView } from '@codemirror/view'
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language'
import { tags } from '@lezer/highlight'
import type { Extension } from '@codemirror/state'

export const jsonDarkTheme = EditorView.theme(
  {
    '&': { backgroundColor: '#111827', color: '#CBD5E1' },
    '.cm-content': {
      caretColor: '#3b82f6',
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      fontSize: '12px',
      lineHeight: '1.6',
    },
    '.cm-cursor': { borderLeftColor: '#3b82f6' },
    '.cm-gutters': { backgroundColor: '#111827', borderRight: '1px solid #24324A', color: '#64748B' },
    '.cm-activeLine': { backgroundColor: '#1E293B' },
    '.cm-activeLineGutter': { backgroundColor: '#1E293B' },
    '&.cm-focused': { outline: 'none' },
    '.cm-selectionBackground': { backgroundColor: '#1e40af40' },
    '.cm-matchingBracket': { backgroundColor: '#1e293b', outline: '1px solid #334155' },
    '.cm-tooltip': { backgroundColor: '#0f1729', border: '1px solid #1e293b', color: '#e2e8f0' },
    '.cm-scroller': { overflowY: 'auto' },
    '.cm-scroller::-webkit-scrollbar': { width: '5px', height: '5px' },
    '.cm-scroller::-webkit-scrollbar-track': { background: 'transparent' },
    '.cm-scroller::-webkit-scrollbar-thumb': { backgroundColor: 'rgba(148, 163, 184, 0.15)', borderRadius: '999px' },
    '.cm-scroller::-webkit-scrollbar-thumb:hover': { backgroundColor: 'rgba(148, 163, 184, 0.35)' },
    '.cm-scroller::-webkit-scrollbar-corner': { background: 'transparent' },
  },
  { dark: true },
)

const jsonHighlightStyle = HighlightStyle.define([
  { tag: tags.propertyName, color: '#93C5FD' },
  { tag: tags.string, color: '#F59E0B' },
  { tag: tags.number, color: '#FDBA74' },
  { tag: [tags.bool, tags.null], color: '#FDBA74' },
  { tag: tags.separator, color: '#93A4B8' },
  { tag: [tags.brace, tags.squareBracket], color: '#93A4B8' },
])

export const jsonSyntaxHighlight: Extension = syntaxHighlighting(jsonHighlightStyle)
