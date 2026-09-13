import { EditorView } from '@codemirror/view'
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language'
import { tags } from '@lezer/highlight'
import type { Extension } from '@codemirror/state'
import {
  woobeCodeTheme,
  woobeRadius,
  woobeSpacing,
  woobeTypography,
  woobeTypographyScale,
} from '../tokens'

export const jsonDarkTheme = EditorView.theme(
  {
    '&': { backgroundColor: woobeCodeTheme.background, color: woobeCodeTheme.foreground },
    '.cm-content': {
      caretColor: woobeCodeTheme.caret,
      fontFamily: woobeTypography.mono.join(', '),
      fontSize: woobeTypographyScale.systemHeading[0],
      lineHeight: woobeTypographyScale.productBody[1].lineHeight,
    },
    '.cm-cursor': { borderLeftColor: woobeCodeTheme.caret },
    '.cm-gutters': {
      backgroundColor: woobeCodeTheme.gutterBackground,
      borderRight: `1px solid ${woobeCodeTheme.border}`,
      color: woobeCodeTheme.gutterForeground,
    },
    '.cm-activeLine': { backgroundColor: woobeCodeTheme.activeLine },
    '.cm-activeLineGutter': { backgroundColor: woobeCodeTheme.activeLine },
    '&.cm-focused': { outline: 'none' },
    '.cm-selectionBackground': { backgroundColor: woobeCodeTheme.selection },
    '.cm-matchingBracket': {
      backgroundColor: woobeCodeTheme.matchingBracketBackground,
      outline: `1px solid ${woobeCodeTheme.matchingBracketBorder}`,
    },
    '.cm-tooltip': {
      backgroundColor: woobeCodeTheme.tooltipBackground,
      border: `1px solid ${woobeCodeTheme.border}`,
      color: woobeCodeTheme.tooltipForeground,
    },
    '.cm-scroller': { overflowY: 'auto' },
    '.cm-scroller::-webkit-scrollbar': { width: woobeSpacing.xs, height: woobeSpacing.xs },
    '.cm-scroller::-webkit-scrollbar-track': { background: 'transparent' },
    '.cm-scroller::-webkit-scrollbar-thumb': {
      backgroundColor: woobeCodeTheme.scrollbar,
      borderRadius: woobeRadius.control,
    },
    '.cm-scroller::-webkit-scrollbar-thumb:hover': { backgroundColor: woobeCodeTheme.scrollbarHover },
    '.cm-scroller::-webkit-scrollbar-corner': { background: 'transparent' },
  },
  { dark: true },
)

const jsonHighlightStyle = HighlightStyle.define([
  { tag: tags.propertyName, color: woobeCodeTheme.syntax.property },
  { tag: tags.string, color: woobeCodeTheme.syntax.string },
  { tag: tags.number, color: woobeCodeTheme.syntax.number },
  { tag: tags.bool, color: woobeCodeTheme.syntax.boolean },
  { tag: tags.null, color: woobeCodeTheme.syntax.null },
  { tag: tags.separator, color: woobeCodeTheme.syntax.punctuation },
  { tag: [tags.brace, tags.squareBracket], color: woobeCodeTheme.syntax.punctuation },
])

export const jsonSyntaxHighlight: Extension = syntaxHighlighting(jsonHighlightStyle)
